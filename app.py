import os, json, sqlite3, uuid, base64, hashlib, re
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
import requests

try:
    import firebase_admin
    from firebase_admin import credentials, auth as fb_auth
except Exception:
    firebase_admin = None

load_dotenv()
BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "samstudy.db"
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
PROFILE_UPLOADS = UPLOADS / "profiles"
PROFILE_UPLOADS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_EMAILS = {x.strip().lower() for x in os.getenv("ADMIN_EMAILS", os.getenv("ADMIN_EMAIL", "samshad0142@gmail.com")).split(",") if x.strip()}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS batches (
          id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, name TEXT NOT NULL,
          description TEXT DEFAULT '', created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, subject TEXT NOT NULL,
          unit TEXT DEFAULT 'All Units', title TEXT NOT NULL, filename TEXT, url TEXT,
          details TEXT DEFAULT '', created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS profiles (
          uid TEXT PRIMARY KEY, email TEXT, name TEXT DEFAULT '', course TEXT DEFAULT '',
          exam TEXT DEFAULT '', photo TEXT DEFAULT '', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS seen_questions (
          uid TEXT NOT NULL, qhash TEXT NOT NULL, question TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(uid,qhash)
        );
        CREATE TABLE IF NOT EXISTS test_attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, exam TEXT, course TEXT,
          subject TEXT, score REAL, accuracy REAL, total INTEGER, duration INTEGER,
          answers_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


def init_firebase_admin():
    if not firebase_admin or firebase_admin._apps:
        return
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
        except Exception as e:
            print("Firebase Admin initialization failed:", e)


init_db()
init_firebase_admin()


def require_user(admin=False):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            token = request.headers.get("Authorization", "")
            if not token.startswith("Bearer "):
                return jsonify(error="Login required."), 401
            if not firebase_admin or not firebase_admin._apps:
                return jsonify(error="Server Firebase Admin is not configured. Add FIREBASE_SERVICE_ACCOUNT_JSON in Render."), 503
            try:
                decoded = fb_auth.verify_id_token(token[7:].strip())
                email = (decoded.get("email") or "").lower()
                if admin and email not in ADMIN_EMAILS:
                    return jsonify(error="Developer/admin access required."), 403
                request.user = decoded
                return fn(*args, **kwargs)
            except Exception as e:
                return jsonify(error=f"Authentication verification failed: {e}"), 401
        return wrapped
    return deco


@app.get("/")
def home():
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", "")
    }
    return render_template("index.html", firebase_config=json.dumps(firebase_config),
                           youtube=os.getenv("YOUTUBE_URL", "https://youtube.com/@sam_malik77"),
                           admin_emails=sorted(ADMIN_EMAILS))


@app.get("/health")
def health():
    return jsonify(ok=True)


@app.get("/api/batches")
def batches():
    with db() as con:
        rows = con.execute("SELECT * FROM batches ORDER BY year, id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/notes")
def notes():
    batch_id = request.args.get("batch_id")
    subject = request.args.get("subject")
    q = "SELECT n.*, b.year, b.name AS batch_name FROM notes n JOIN batches b ON b.id=n.batch_id"
    clauses, params = [], []
    if batch_id:
        clauses.append("n.batch_id=?"); params.append(batch_id)
    if subject:
        clauses.append("LOWER(n.subject)=LOWER(?)"); params.append(subject)
    if clauses: q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY n.subject, n.unit, n.id DESC"
    with db() as con:
        rows = con.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(UPLOADS, name, as_attachment=True)


@app.post("/api/admin/batches")
@require_user(admin=True)
def add_batch():
    d = request.get_json(force=True)
    try: year = int(d.get("year", 0))
    except: year = 0
    name = (d.get("name") or "").strip()
    desc = (d.get("description") or "").strip()
    if year not in (1,2,3,4) or not name:
        return jsonify(error="Year and batch name are required."), 400
    with db() as con:
        cur = con.execute("INSERT INTO batches(year,name,description,created_by) VALUES(?,?,?,?)",
                          (year,name,desc,request.user.get("email")))
        con.commit()
    return jsonify(ok=True,id=cur.lastrowid)


@app.post("/api/admin/notes")
@require_user(admin=True)
def add_note():
    batch_id=request.form.get("batch_id"); subject=request.form.get("subject","").strip()
    unit=request.form.get("unit","All Units").strip(); title=request.form.get("title","").strip()
    url=request.form.get("url","").strip(); details=request.form.get("details","").strip()
    if not batch_id or not subject or not title:
        return jsonify(error="Batch, subject and title are required."),400
    filename=None
    file=request.files.get("file")
    if file and file.filename:
        ext=Path(file.filename).suffix.lower()
        if ext not in {".pdf",".doc",".docx",".ppt",".pptx",".txt",".zip"}:
            return jsonify(error="Use PDF/DOC/PPT/TXT/ZIP for notes."),400
        filename=f"{uuid.uuid4().hex}{ext}"
        file.save(UPLOADS/filename)
    with db() as con:
        con.execute("""INSERT INTO notes(batch_id,subject,unit,title,filename,url,details,created_by)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (batch_id,subject,unit,title,filename,url,details,request.user.get("email")))
        con.commit()
    return jsonify(ok=True)


@app.get("/api/profile")
@require_user()
def get_profile():
    uid=request.user["uid"]
    with db() as con:
        r=con.execute("SELECT * FROM profiles WHERE uid=?", (uid,)).fetchone()
    if r:
        return jsonify(profile=dict(r), email=request.user.get("email",""), verified=bool(request.user.get("email_verified")))
    return jsonify(profile={"uid":uid,"email":request.user.get("email",""),"name":request.user.get("name",""),
                            "course":"","exam":"","photo":request.user.get("picture","")},
                   email=request.user.get("email",""), verified=bool(request.user.get("email_verified")))


@app.post("/api/profile")
@require_user()
def save_profile():
    uid=request.user["uid"]; email=(request.user.get("email") or "").lower()
    name=(request.form.get("name") or "").strip()
    course=(request.form.get("course") or "").strip()
    exam=(request.form.get("exam") or "").strip()
    photo=""
    file=request.files.get("photo")
    if file and file.filename:
        ext=Path(file.filename).suffix.lower()
        if ext not in {".jpg",".jpeg",".png",".webp"}:
            return jsonify(error="Profile photo must be JPG, PNG or WEBP."),400
        filename=f"profile_{hashlib.sha256(uid.encode()).hexdigest()[:20]}{ext}"
        file.save(PROFILE_UPLOADS/filename)
        photo=f"/uploads/profiles/{filename}"
    with db() as con:
        old=con.execute("SELECT photo FROM profiles WHERE uid=?", (uid,)).fetchone()
        if not photo and old: photo=old["photo"] or ""
        con.execute("""INSERT INTO profiles(uid,email,name,course,exam,photo) VALUES(?,?,?,?,?,?)
                       ON CONFLICT(uid) DO UPDATE SET email=excluded.email,name=excluded.name,
                       course=excluded.course,exam=excluded.exam,photo=excluded.photo,
                       updated_at=CURRENT_TIMESTAMP""",
                    (uid,email,name,course,exam,photo))
        con.commit()
    return jsonify(ok=True, profile={"uid":uid,"email":email,"name":name,"course":course,"exam":exam,"photo":photo})


@app.post("/api/ai/doubt")
def ai_doubt():
    d=request.get_json(force=True); doubt=(d.get("doubt") or "").strip()
    image_data=d.get("image")
    if not doubt and not image_data: return jsonify(error="Type a doubt or upload an image."),400
    prompt="""You are SamStudy AI. Solve the student's academic doubt accurately.
Give a clear step-by-step explanation, formulas/calculations where useful, then a final answer.
If an image is supplied, read the problem from it. Never claim a result you cannot infer."""
    parts=[{"text":prompt + "\nStudent text: " + (doubt or "(image only)") }]
    if image_data and "," in image_data:
        header,data=image_data.split(",",1)
        mime=re.search(r"data:(.*?);base64",header)
        if mime:
            parts.append({"inline_data":{"mime_type":mime.group(1),"data":data}})
    text,err=gemini_parts(parts)
    if err: return jsonify(error=err),503
    return jsonify(answer=text)


def gemini_parts(parts):
    key=os.getenv("GEMINI_API_KEY","").strip()
    model=os.getenv("GEMINI_MODEL","gemini-2.5-flash").strip()
    if not key: return None,"GEMINI_API_KEY is not configured on Render."
    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    try:
        r=requests.post(url,json={"contents":[{"parts":parts}],"generationConfig":{"temperature":0.35}},timeout=60)
        if r.status_code!=200:
            return None,f"AI service error ({r.status_code})."
        data=r.json()
        text=data["candidates"][0]["content"]["parts"][0]["text"]
        return text,None
    except Exception as e:
        return None,str(e)


def seen_for(uid):
    with db() as con:
        return [r["question"] for r in con.execute("SELECT question FROM seen_questions WHERE uid=? ORDER BY created_at DESC LIMIT 250",(uid,)).fetchall()]


def parse_json(text):
    cleaned=text.strip()
    cleaned=re.sub(r"^```(?:json)?\s*|\s*```$","",cleaned,flags=re.I)
    return json.loads(cleaned)


@app.post("/api/ai/quiz")
@require_user()
def ai_quiz():
    d=request.get_json(force=True)
    course=d.get("course") or "B.Tech"; exam=d.get("exam") or "JEE Main"
    subject=d.get("subject") or "General"; count=max(1,min(int(d.get("count",10)),50))
    difficulty=d.get("difficulty") or "Mixed"; uid=request.user["uid"]
    seen=seen_for(uid)
    avoid="\n".join(f"- {x}" for x in seen[-120:])
    prompt=f"""Create {count} high-quality MCQs for {course} students preparing for {exam}.
Subject: {subject}. Difficulty: {difficulty}.
Prioritize official/known PYQ concepts and exam pattern. You may include clearly labelled PYQ-style questions,
but do not falsely attribute a question to a year unless certain. Avoid repeating any prior questions listed below.
Return ONLY a JSON array. Each item must be:
{{"question":"...","options":["A","B","C","D"],"answer":0,"explanation":"detailed solution",
"source":"PYQ / PYQ-style / Original"}}
The answer is a zero-based option index.
Previously seen questions:
{avoid or "(none)"}
"""
    text,err=gemini_parts([{"text":prompt}])
    if err:return jsonify(error=err),503
    try:
        qs=parse_json(text)
        cleaned=[]; local_hashes=set()
        with db() as con:
            for q in qs:
                q["question"]=str(q.get("question","")).strip()
                q["options"]=q.get("options",[])[:4]
                if len(q["options"])!=4 or not q["question"]: continue
                q["answer"]=int(q.get("answer",0))
                if q["answer"] not in range(4): continue
                q["explanation"]=str(q.get("explanation",""))
                q["source"]=str(q.get("source","AI"))
                h=hashlib.sha256(q["question"].strip().lower().encode()).hexdigest()
                if h in local_hashes or con.execute("SELECT 1 FROM seen_questions WHERE uid=? AND qhash=?",(uid,h)).fetchone():
                    continue
                local_hashes.add(h)
                con.execute("INSERT INTO seen_questions(uid,qhash,question) VALUES(?,?,?)",(uid,h,q["question"]))
                cleaned.append(q)
                if len(cleaned)>=count: break
            con.commit()
        return jsonify(questions=cleaned)
    except Exception:
        return jsonify(error="AI returned an invalid quiz format. Please try again."),502


@app.post("/api/ai/test")
@require_user()
def ai_test():
    d=request.get_json(force=True)
    course=d.get("course") or "B.Tech"; exam=d.get("exam") or "JEE Main"; subject=d.get("subject") or "General"
    count=max(5,min(int(d.get("count",20)),100)); difficulty=d.get("difficulty") or "Real exam"
    prompt=f"""Create a realistic {exam} practice test for {course}, subject {subject}.
Question count {count}, level {difficulty}. Mimic the real exam's style, difficulty, options and marking concept,
without reproducing copyrighted material verbatim. Prefer PYQ concepts and original questions.
Return ONLY JSON array with objects:
{{"question":"...","options":["A","B","C","D"],"answer":0,"explanation":"detailed solution",
"marks":1,"negative":0,"level":"Easy|Medium|Hard"}}"""
    text,err=gemini_parts([{"text":prompt}])
    if err:return jsonify(error=err),503
    try:return jsonify(questions=parse_json(text)[:count])
    except:return jsonify(error="AI returned an invalid test format. Please try again."),502


@app.post("/api/test/submit")
@require_user()
def submit_test():
    d=request.get_json(force=True); qs=d.get("questions",[]); answers=d.get("answers",{})
    duration=int(d.get("duration",0)); score=0; maxmarks=0; correct=0
    results=[]
    for i,q in enumerate(qs):
        marks=float(q.get("marks",1)); neg=float(q.get("negative",0)); maxmarks+=marks
        a=answers.get(str(i)); ok=a is not None and int(a)==int(q.get("answer",0))
        if ok: score+=marks; correct+=1
        elif a is not None: score-=neg
        results.append({"correct":ok,"selected":a,"answer":q.get("answer"),"explanation":q.get("explanation",""),
                        "level":q.get("level",""),"marks":marks,"negative":neg})
    accuracy=(correct/len(qs)*100) if qs else 0
    with db() as con:
        con.execute("""INSERT INTO test_attempts(uid,exam,course,subject,score,accuracy,total,duration,answers_json)
                       VALUES(?,?,?,?,?,?,?,?,?)""",(request.user["uid"],d.get("exam"),d.get("course"),d.get("subject"),
                                                        score,accuracy,len(qs),duration,json.dumps(results)))
        con.commit()
    return jsonify(score=score,max_marks=maxmarks,accuracy=accuracy,total=len(qs),duration=duration,results=results)


if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
