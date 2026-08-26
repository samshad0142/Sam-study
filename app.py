import os, json, re, sqlite3, base64, secrets
from pathlib import Path
from functools import wraps
from datetime import datetime
from io import BytesIO
from urllib.parse import quote_plus

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, abort, session

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
STATIC = ROOT / 'static'
TEMPLATES = ROOT / 'templates'
UPLOADS = DATA / 'uploads'
BOOKS = UPLOADS / 'books'
CONTENT = UPLOADS / 'content'
GENERATED = DATA / 'generated'
for p in (DATA, UPLOADS, BOOKS, CONTENT, GENERATED):
    p.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATES), static_folder=str(STATIC), static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'samshad0142@gmail.com').strip().lower()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '').strip()
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip()
YOUTUBE_URL = os.getenv('YOUTUBE_URL', 'https://www.youtube.com/@Sam_malik77')
INSTAGRAM_URL = os.getenv('INSTAGRAM_URL', 'https://www.instagram.com/Sam_shad132/')

DB = DATA / 'samstudy.db'
CHANGES = DATA / 'changes.json'
CATALOG_FILE = DATA / 'catalog.json'
CHAPTERS_FILE = DATA / 'chapters.json'
if not CHANGES.exists(): CHANGES.write_text('[]', encoding='utf-8')

def load_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

CATALOG = load_json(CATALOG_FILE, {'exams': {}, 'courses': {}})
CHAPTERS = load_json(CHAPTERS_FILE, {})

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      name TEXT DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS progress(
      uid TEXT NOT NULL, resource TEXT NOT NULL, value REAL NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL, PRIMARY KEY(uid, resource)
    );
    CREATE TABLE IF NOT EXISTS shield_rules(
      id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, app_name TEXT NOT NULL,
      minutes INTEGER NOT NULL DEFAULT 60, reset_time TEXT NOT NULL DEFAULT '00:00',
      enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
    );
    ''')
    if ADMIN_PASSWORD:
        row = con.execute('SELECT id FROM users WHERE email=?', (ADMIN_EMAIL,)).fetchone()
        if not row:
            con.execute('INSERT INTO users(email,password_hash,name,created_at) VALUES(?,?,?,?)', (ADMIN_EMAIL,password_hash(ADMIN_PASSWORD),'SamStudy Developer',datetime.utcnow().isoformat()))
        con.commit()
    con.close()


def password_hash(password):
    import hashlib
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 180000)
    return salt.hex() + '$' + digest.hex()

def password_ok(password, stored):
    import hashlib, hmac
    try:
        salt_hex, digest_hex = stored.split('$', 1)
        got = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 180000).hex()
        return hmac.compare_digest(got, digest_hex)
    except Exception:
        return False

init_db()

def current_local_user():
    uid = session.get('uid')
    if not uid: return None
    con = db(); row = con.execute('SELECT id,email,name FROM users WHERE id=?', (uid,)).fetchone(); con.close()
    if not row: return None
    return {'uid': str(row['id']), 'email': row['email'], 'name': row['name'] or '', 'emailVerified': True, 'local': True}

def firebase_user_from_token(token):
    if not token: return None
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        if not firebase_admin._apps:
            raw = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON_B64', '').strip()
            raw_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
            if raw:
                info = json.loads(base64.b64decode(raw).decode())
                firebase_admin.initialize_app(credentials.Certificate(info))
            elif raw_json:
                firebase_admin.initialize_app(credentials.Certificate(json.loads(raw_json)))
            else:
                return None
        u = auth.verify_id_token(token)
        return {'uid': u.get('uid'), 'email': (u.get('email') or '').lower(), 'name': u.get('name') or '', 'emailVerified': bool(u.get('email_verified'))}
    except Exception:
        return None

def request_user():
    authz = request.headers.get('Authorization', '')
    if authz.startswith('Bearer '):
        u = firebase_user_from_token(authz[7:])
        if u: return u
    return current_local_user()

def require_user(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not request_user(): return jsonify(error='Login required'), 401
        return fn(*args, **kwargs)
    return wrapper

def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = request_user()
        if not u or (u.get('email') or '').lower() != ADMIN_EMAIL:
            return jsonify(error='Developer access required. Sign in with the configured admin account.'), 403
        return fn(*args, **kwargs)
    return wrapper


def gemini(prompt, *, image_bytes=None, image_mime='image/jpeg', json_mode=False, grounded=False):
    if not GEMINI_KEY:
        raise RuntimeError('GEMINI_API_KEY is not configured in Render Environment Variables.')
    import requests
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
    parts = [{'text': prompt}]
    if image_bytes:
        import base64 as b64
        parts.append({'inlineData': {'mimeType': image_mime, 'data': b64.b64encode(image_bytes).decode()}})
    body = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': 0.2,
            **({'responseMimeType': 'application/json'} if json_mode else {})
        }
    }
    if grounded:
        body['tools'] = [{'google_search': {}}]
    r = requests.post(url, params={'key': GEMINI_KEY}, json=body, timeout=180)
    if not r.ok: raise RuntimeError(f'Gemini API error {r.status_code}: {r.text[:700]}')
    data = r.json()
    try:
        return data['candidates'][0]['content']['parts'][0]['text'], data
    except Exception:
        raise RuntimeError('Gemini returned no usable answer.')

def parse_json(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip(), flags=re.I)
    text = re.sub(r'\s*```$', '', text).strip()
    return json.loads(text)

def allocation(n, pattern=None):
    comp = (pattern or {}).get('composition') or {}
    if comp and sum(int(comp.get(k, 0)) for k in ('pyq','typed','hard')) == n:
        return int(comp.get('pyq',0)), int(comp.get('typed',0)), int(comp.get('hard',0))
    a, b = round(n*.60), round(n*.30)
    c = n - a - b
    return a, b, max(0,c)

DEFAULT_QUESTIONS = [
 {'question':'If a number is increased by 20%, the result is 240. What was the original number?','options':['180','200','220','210'],'answer':1,'explanation':'Let the original number be x. Then 1.2x = 240, so x = 200.','subject':'Quantitative Aptitude'},
 {'question':'Which data structure follows the FIFO principle?','options':['Stack','Queue','Tree','Graph'],'answer':1,'explanation':'FIFO means First In, First Out, which is the defining behavior of a queue.','subject':'Data Structures'},
 {'question':'What is the derivative of x²?','options':['x','2x','x²','2'],'answer':1,'explanation':'Using the power rule, d(x²)/dx = 2x.','subject':'Mathematics'},
 {'question':'Which gas is most abundant in Earth’s atmosphere?','options':['Oxygen','Nitrogen','Carbon dioxide','Hydrogen'],'answer':1,'explanation':'Nitrogen makes up about 78% of dry Earth atmosphere.','subject':'General Awareness'},
 {'question':'Solve: x² − 5x + 6 = 0.','options':['x=1,6','x=2,3','x=−2,−3','x=0,5'],'answer':1,'explanation':'Factor: (x−2)(x−3)=0, so x=2 or 3.','subject':'Mathematics'},
]

def fallback_questions(n, exam, etype, subjects):
    out=[]
    for i in range(n):
        q=dict(DEFAULT_QUESTIONS[i % len(DEFAULT_QUESTIONS)])
        q['sourceType']='PYQ-type'
        q['source']='SamStudy fallback practice'
        q['question']=q['question'].replace('SSC CGL 2024', exam)
        if subjects: q['subject']=subjects[i % len(subjects)]
        out.append(q)
    return out

# ---------- pages ----------
@app.get('/')
def home(): return render_template('index.html', initial_page='home')
@app.get('/preview')
def preview(): return render_template('index.html', initial_page='home')
@app.get('/health')
def health():
    return jsonify(ok=True, ai=bool(GEMINI_KEY), localLogin=True, firebase=bool(os.getenv('FIREBASE_API_KEY')))

@app.get('/<page>')
def page_alias(page):
    targets = {'login':'profile','signup':'profile','test':'test','tests':'test','doubt':'ai','three-d':'three','notes':'resource','resource':'resource','studyshield':'shield','shield':'shield','ai':'ai'}
    if page in targets or page in {'batches','subjects','quiz','profile','admin'}:
        return render_template('index.html', initial_page=targets.get(page,page))
    abort(404)

@app.get('/manifest.webmanifest')
def manifest(): return send_from_directory(ROOT, 'manifest.webmanifest')

# ---------- auth ----------
@app.post('/api/auth/register')
def register():
    d=request.get_json(silent=True) or {}; email=str(d.get('email','')).strip().lower(); password=str(d.get('password','')); name=str(d.get('name','')).strip()
    if not email or '@' not in email or len(password)<6: return jsonify(error='Enter a valid email and a password of at least 6 characters.'),400
    if email == ADMIN_EMAIL and ADMIN_PASSWORD and password != ADMIN_PASSWORD: return jsonify(error='This email is reserved for the SamStudy developer account.'),403
    con=db()
    try:
        cur=con.execute('INSERT INTO users(email,password_hash,name,created_at) VALUES(?,?,?,?)',(email,password_hash(password),name,datetime.utcnow().isoformat())); con.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError: con.close(); return jsonify(error='An account with this email already exists.'),409
    con.close(); session['uid']=uid
    return jsonify(user={'uid':str(uid),'email':email,'name':name,'emailVerified':True,'local':True})

@app.post('/api/auth/login')
def login_local():
    d=request.get_json(silent=True) or {}; email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
    con=db(); row=con.execute('SELECT id,email,password_hash,name FROM users WHERE email=?',(email,)).fetchone(); con.close()
    if not row or not password_ok(password,row['password_hash']): return jsonify(error='Invalid email or password.'),401
    session['uid']=row['id']
    return jsonify(user={'uid':str(row['id']),'email':row['email'],'name':row['name'] or '', 'emailVerified':True,'local':True})

@app.post('/api/auth/logout')
def logout_local(): session.clear(); return jsonify(ok=True)

@app.get('/api/auth/me')
def auth_me(): return jsonify(user=request_user())

# ---------- config/content ----------
@app.get('/api/config')
def config():
    keys=['apiKey','authDomain','projectId','storageBucket','messagingSenderId','appId']
    firebase={k:os.getenv('FIREBASE_'+k.upper(),'').strip() for k in keys}
    # Correct environment variable casing used by Render.
    firebase={'apiKey':os.getenv('FIREBASE_API_KEY',''),'authDomain':os.getenv('FIREBASE_AUTH_DOMAIN',''),'projectId':os.getenv('FIREBASE_PROJECT_ID',''),'storageBucket':os.getenv('FIREBASE_STORAGE_BUCKET',''),'messagingSenderId':os.getenv('FIREBASE_MESSAGING_SENDER_ID',''),'appId':os.getenv('FIREBASE_APP_ID','')}
    return jsonify(firebase=firebase,firebaseConfigured=all(firebase.values()),adminEmail=ADMIN_EMAIL,geminiConfigured=bool(GEMINI_KEY),geminiModel=GEMINI_MODEL,youtube=YOUTUBE_URL,instagram=INSTAGRAM_URL,localLogin=True)

@app.get('/api/catalog')
def catalog(): return jsonify(CATALOG)

@app.get('/api/chapters')
def chapters():
    subject=(request.args.get('subject') or '').strip()
    fallback=['Introduction','Core Concepts','Important Definitions','Key Formulas / Rules','Solved Examples','Common Mistakes','Practice Questions','Revision']
    return jsonify(subject=subject,chapters=CHAPTERS.get(subject,fallback))

def changes(): return load_json(CHANGES, [])
def save_changes(arr): CHANGES.write_text(json.dumps(arr,ensure_ascii=False,indent=2),encoding='utf-8')
@app.get('/api/catalog-changes')
def catalog_changes(): return jsonify(changes())

@app.get('/api/resources')
def resources():
    arr=changes()
    uploaded=[]
    for p in CONTENT.rglob('*'):
        if p.is_file(): uploaded.append({'kind':'resource','resourceKind':'Notes','subject':'','name':p.name,'url':'/content/'+quote_plus(str(p.relative_to(CONTENT)).replace('\\','/')).replace('%2F','/')})
    return jsonify(arr + uploaded)

@app.get('/content/<path:name>')
def content(name): return send_from_directory(CONTENT,name,as_attachment=False)
@app.get('/books/<path:name>')
def books(name): return send_from_directory(BOOKS,name,as_attachment=False)

# ---------- AI quiz/test ----------
@app.post('/api/ai/quiz')
def ai_quiz():
    d=request.get_json(silent=True) or {}; mode=d.get('mode','quiz'); n=max(1,min(int(d.get('count',10)),200)); exam=str(d.get('exam','SSC')); etype=str(d.get('type','')); subjects=d.get('subjects') or []; pattern=d.get('pattern') or {}
    pyq,typed,hard=allocation(n,pattern if mode=='test' else None)
    composition=f'exactly {pyq} PYQ, {typed} PYQ-type, {hard} HARDEST' if n else ''
    prompt=f'''You are SamStudy's exam engine. Create exactly {n} MCQs for {exam} — {etype}. Subjects: {", ".join(subjects) or "mixed"}.\nComposition: {composition}.\nFor each item return question, options (exactly 4), answer (0-3), explanation, subject, sourceType, source. Use sourceType PYQ only when you can confidently verify the past question; otherwise use PYQ-type. Never invent a PYQ citation. Use clean mathematical notation (Unicode or LaTeX), no decorative symbols. For test mode follow this official-style pattern: {json.dumps(pattern,ensure_ascii=False)}. Return JSON array only.'''
    try:
        text,_=gemini(prompt,json_mode=True,grounded=True); data=parse_json(text)
        if not isinstance(data,list): raise ValueError('Invalid question JSON')
        return jsonify(questions=data[:n],source='Gemini')
    except Exception as e:
        return jsonify(questions=fallback_questions(n,exam,etype,subjects),source='Offline safe bank',warning=str(e))

# Alias kept for compatibility with older versions.
@app.post('/api/quiz')
def quiz_alias(): return ai_quiz()

# ---------- AI doubt / 3D ----------
@app.post('/api/ai/doubt')
def ai_doubt():
    q=''; image=None; mime='image/jpeg'
    if request.files:
        q=(request.form.get('question') or '').strip(); f=request.files.get('image')
        if f: image=f.read(); mime=f.mimetype or mime
    else:
        d=request.get_json(silent=True) or {}; q=str(d.get('question','')).strip(); img=d.get('image') or {}
        if img.get('data'):
            import base64 as b64
            try: image=b64.b64decode(img['data']); mime=img.get('mimeType') or mime
            except Exception: pass
    if not q and not image: return jsonify(error='Enter a doubt or attach a photo.'),400
    prompt=rf'''You are SamStudy AI tutor. Solve the student's doubt step by step. Student track: {(request.form.get("track") if request.form else "")}. Use proper mathematical notation such as x², √, ≤, ≥, ∑ or LaTeX \\(....\). Do not add decorative or unwanted symbols. If a fact depends on a source, say what should be verified. Question: {q or "Solve the attached image."}'''
    try:
        text,_=gemini(prompt,image_bytes=image,image_mime=mime,grounded=True)
        return jsonify(answer=text,source='Gemini')
    except Exception as e:
        return jsonify(answer='AI is not configured yet. Add GEMINI_API_KEY in Render Environment Variables.',source='Setup required',warning=str(e))

@app.post('/api/ai/3d')
def ai_3d():
    d=request.get_json(silent=True) or {}; concept=str(d.get('concept','')).strip()
    if not concept: return jsonify(error='Enter a concept.'),400
    prompt=f'''Create a concise educational 3D scene for the concept "{concept}". Return JSON with title, explanation and objects. Each object must have type (box, sphere, cylinder, torus, plane, arrow), x, y, z, scale, color, label. Max 12 objects. The scene should visually explain the concept, not merely decorate it.'''
    try:
        text,_=gemini(prompt,json_mode=True); scene=parse_json(text)
        return jsonify(title=scene.get('title',concept),explanation=scene.get('explanation',''),scene=scene,source='Gemini')
    except Exception as e:
        return jsonify(title=concept,explanation='Interactive fallback scene. Add GEMINI_API_KEY for concept-specific generation.',scene={'objects':[{'type':'sphere','x':0,'y':0,'z':0,'scale':1.2,'color':'#168cff','label':concept},{'type':'arrow','x':0,'y':1.6,'z':0,'scale':1,'color':'#ffd166','label':'Direction'}]},source='Fallback',warning=str(e))

@app.post('/api/ai/notes')
def ai_notes():
    d=request.get_json(silent=True) or {}; subject=str(d.get('subject','')).strip(); chapter=str(d.get('chapter','')).strip(); exam=str(d.get('exam','')); etype=str(d.get('type',''))
    if not subject or not chapter: return jsonify(error='Subject and chapter are required.'),400
    prompt=f'''Create structured study notes for {exam} {etype}, subject {subject}, chapter {chapter}. Use headings, definitions, formulas, solved examples, common mistakes and quick revision. Mathematical expressions must be clean LaTeX or Unicode. Do not use decorative symbols. If source verification is requested, distinguish textbook knowledge from verified sources.'''
    try:
        text,_=gemini(prompt,grounded=True)
    except Exception as e:
        text=f'{chapter}\n\nKey concepts\n- Review the core definitions and formulas for this chapter.\n- Add examples from your prescribed textbook.\n\nAI status: {e}'
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        path=GENERATED / f'notes_{secrets.token_hex(8)}.pdf'
        doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42)
        styles=getSampleStyleSheet(); story=[Paragraph('SamStudy — Chapter Notes',styles['Title']),Spacer(1,12),Paragraph(f'{subject} — {chapter}',styles['Heading2']),Spacer(1,8)]
        for block in re.split(r'\n\s*\n',text):
            clean=re.sub(r'[<>]','',block).replace('&','&amp;').replace('\n','<br/>')
            story.append(Paragraph(clean,styles['BodyText'])); story.append(Spacer(1,8))
        doc.build(story)
        return jsonify(download=f'/generated/{path.name}',text=text,source='Gemini')
    except Exception as e: return jsonify(error=f'PDF generation failed: {e}'),500

@app.get('/generated/<path:name>')
def generated(name): return send_from_directory(GENERATED,name,as_attachment=True)

# ---------- lectures ----------
@app.get('/api/lectures')
def lectures():
    subject=(request.args.get('subject') or '').strip(); chapter=(request.args.get('chapter') or '').strip(); etype=(request.args.get('type') or '').strip()
    query=' '.join(x for x in ['SamStudy',etype,subject,chapter,'lecture'] if x)
    return jsonify(url='https://www.youtube.com/results?search_query='+quote_plus(query),query=query)

# ---------- book verification + PDF ----------
@app.post('/api/books/verify')
def verify_book():
    d=request.get_json(silent=True) or {}; question=str(d.get('question','')).strip(); filename=str(d.get('book','')).strip()
    if not question or not filename: return jsonify(error='Question and book filename are required.'),400
    path=BOOKS / Path(filename).name
    if not path.exists(): return jsonify(error='Book not found. Upload it from Developer Panel first.'),404
    try:
        from pypdf import PdfReader
        reader=PdfReader(str(path)); terms=[t.lower() for t in re.findall(r'[A-Za-z]{4,}',question)]; hits=[]
        for i,p in enumerate(reader.pages):
            txt=p.extract_text() or ''; low=txt.lower(); score=sum(low.count(t) for t in terms[:12])
            if score: hits.append((score,i+1,txt[:5000]))
        hits=sorted(hits,reverse=True)[:5]
        evidence='\n\n'.join(f'[Book page {p}]\n{t}' for _,p,t in hits)
        prompt=f'''Answer using only these book excerpts. Question: {question}\n{evidence or "No matching excerpt found."}\nClearly state if evidence is insufficient and include a Sources section with page numbers.'''
        text,_=gemini(prompt,grounded=False)
        return jsonify(answer=text,book=path.name,pages=[p for _,p,_ in hits],source='Uploaded book + Gemini')
    except Exception as e: return jsonify(error=str(e)),500

@app.post('/api/doubt/pdf')
def doubt_pdf():
    d=request.get_json(silent=True) or {}; answer=str(d.get('answer','')).strip(); question=str(d.get('question','')).strip()
    if not answer: return jsonify(error='No answer supplied.'),400
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        path=GENERATED / f'doubt_{secrets.token_hex(8)}.pdf'
        doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42)
        styles=getSampleStyleSheet(); story=[Paragraph('SamStudy — AI Doubt Solution',styles['Title']),Spacer(1,12)]
        if question: story += [Paragraph('Question',styles['Heading2']),Paragraph(re.sub(r'[<>]','',question),styles['BodyText']),Spacer(1,10)]
        clean=re.sub(r'[<>]','',answer).replace('&','&amp;').replace('\n','<br/>')
        story += [Paragraph('Solution',styles['Heading2']),Paragraph(clean,styles['BodyText']),Spacer(1,12),Paragraph('Generated with SamStudy AI. Verify important facts against cited material.',styles['Italic'])]
        doc.build(story)
        return jsonify(download=f'/generated/{path.name}')
    except Exception as e: return jsonify(error=str(e)),500

# ---------- developer content ----------
@app.post('/api/admin/batch')
@require_admin
def admin_batch():
    d=request.get_json(silent=True) or {}; name=str(d.get('name','')).strip(); parent=str(d.get('parent','')).strip(); etype=str(d.get('type','')).strip()
    if not name or not parent or not etype: return jsonify(error='Batch name, course/exam and type are required.'),400
    arr=changes(); arr.append({'kind':'batch','name':name,'parent':parent,'type':etype,'createdAt':datetime.utcnow().isoformat()}); save_changes(arr); return jsonify(ok=True)

@app.post('/api/admin/resource')
@require_admin
def admin_resource():
    d=request.get_json(silent=True) or {}; url=str(d.get('url','')).strip(); subject=str(d.get('subject','')).strip(); parent=str(d.get('parent','')).strip(); etype=str(d.get('type','')).strip(); kind=str(d.get('resourceKind','Notes')).strip()
    if not url or not subject: return jsonify(error='Resource URL and subject are required.'),400
    arr=changes(); arr.append({'kind':'resource','resourceKind':kind,'subject':subject,'parent':parent,'type':etype,'url':url,'createdAt':datetime.utcnow().isoformat()}); save_changes(arr); return jsonify(ok=True)

@app.post('/api/admin/upload')
@require_admin
def admin_upload():
    f=request.files.get('file'); kind=request.form.get('kind','content')
    if not f or not f.filename: return jsonify(error='Choose a file.'),400
    safe=re.sub(r'[^A-Za-z0-9._-]+','_',f.filename); target=BOOKS if kind=='book' else CONTENT; f.save(target/safe)
    return jsonify(ok=True,name=safe,url=('/books/' if kind=='book' else '/content/')+safe)

# ---------- StudyShield / progress ----------
@app.get('/api/shield')
@require_user
def shield_get():
    u=request_user(); con=db(); rows=con.execute('SELECT * FROM shield_rules WHERE uid=? ORDER BY app_name',(u['uid'],)).fetchall(); con.close(); return jsonify(rules=[dict(r) for r in rows])

@app.post('/api/shield')
@require_user
def shield_save():
    u=request_user(); d=request.get_json(silent=True) or {}; name=str(d.get('app_name','')).strip(); mins=max(1,min(int(d.get('minutes',60)),1440)); reset=str(d.get('reset_time','00:00'))
    if not name: return jsonify(error='App name required.'),400
    con=db(); cur=con.execute('INSERT INTO shield_rules(uid,app_name,minutes,reset_time,created_at) VALUES(?,?,?,?,?)',(u['uid'],name,mins,reset,datetime.utcnow().isoformat())); con.commit(); rid=cur.lastrowid; con.close(); return jsonify(ok=True,id=rid)

@app.delete('/api/shield/<int:rule_id>')
@require_user
def shield_delete(rule_id):
    u=request_user(); con=db(); con.execute('DELETE FROM shield_rules WHERE id=? AND uid=?',(rule_id,u['uid'])); con.commit(); con.close(); return jsonify(ok=True)

@app.post('/api/progress')
@require_user
def progress_save():
    u=request_user(); d=request.get_json(silent=True) or {}; resource=str(d.get('resource','')); value=float(d.get('value',0))
    if not resource: return jsonify(error='Resource required.'),400
    con=db(); con.execute('INSERT INTO progress(uid,resource,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(uid,resource) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(u['uid'],resource,value,datetime.utcnow().isoformat())); con.commit(); con.close(); return jsonify(ok=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT','5000')), debug=False)
