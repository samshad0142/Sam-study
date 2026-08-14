
import os
import json
import random
import re
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from firebase_admin import credentials, firestore, initialize_app, auth as fb_auth
import firebase_admin

try:
    from google import genai
except Exception:
    genai = None

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "samshad0142@gmail.com").strip().lower()
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "sam-study-e9481")

# ---------- Firebase Admin ----------
firebase_ready = False
db = None

def init_firebase():
    global firebase_ready, db
    if firebase_ready:
        return True

    try:
        service_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        service_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

        if service_json:
            cred = credentials.Certificate(json.loads(service_json))
        elif service_file and Path(service_file).exists():
            cred = credentials.Certificate(service_file)
        else:
            # Useful for local development when ADC is already configured.
            cred = credentials.ApplicationDefault()

        initialize_app(cred, {"projectId": FIREBASE_PROJECT_ID})
        db = firestore.client()
        firebase_ready = True
        return True
    except Exception as exc:
        app.logger.warning("Firebase Admin not ready: %s", exc)
        return False

init_firebase()

# ---------- Firebase web config ----------
@app.get("/api/firebase-config")
def firebase_config():
    # The API key is intentionally supplied through Render environment variables.
    # Never commit a private service-account key to GitHub.
    return jsonify({
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", f"{FIREBASE_PROJECT_ID}.firebaseapp.com"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", FIREBASE_PROJECT_ID),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
    })

# ---------- auth helpers ----------
def bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.split(" ", 1)[1].strip()

def current_user(required=True):
    token = bearer_token()
    if not token:
        if required:
            abort(401, description="Authentication required.")
        return None

    if not init_firebase():
        if required:
            abort(503, description="Firebase Admin is not configured on the server.")
        return None

    try:
        return fb_auth.verify_id_token(token)
    except Exception:
        if required:
            abort(401, description="Invalid or expired Firebase session.")
        return None

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user(True)
        email = (user.get("email") or "").lower()
        if email != ADMIN_EMAIL:
            abort(403, description="Developer/admin access required.")
        return fn(*args, **kwargs)
    return wrapped

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
def api_error(err):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": getattr(err, "description", str(err))}), err.code
    return err

# ---------- pages ----------
@app.get("/")
def home():
    return render_template("index.html")

@app.get("/login")
def login():
    return render_template("login.html")

@app.get("/signup")
def signup():
    return render_template("signup.html")

@app.get("/batches")
def batches():
    return render_template("batches.html", subjects=YEAR_SUBJECTS)

@app.get("/notes")
def notes():
    return render_template("notes.html")

@app.get("/quiz")
def quiz():
    return render_template("quiz.html")

@app.get("/doubt")
def doubt():
    return render_template("doubt.html")

@app.get("/3d")
def three_d():
    return render_template("three_d.html")

@app.get("/admin")
def admin():
    return render_template("admin.html")

# ---------- public content ----------
YEAR_SUBJECTS = {
    "1": [
        "Engineering Mathematics-I", "Engineering Physics", "Engineering Chemistry",
        "Programming for Problem Solving", "Fundamentals of Electrical Engineering",
        "Fundamentals of Electronics Engineering", "Environment & Ecology"
    ],
    "2": [
        "Engineering Mathematics-III", "Data Structures", "Discrete Mathematics",
        "Object Oriented Programming", "Digital Logic Design", "Computer Organization",
        "Operating Systems"
    ],
    "3": [
        "Design & Analysis of Algorithms", "Database Management Systems",
        "Computer Networks", "Theory of Computation", "Software Engineering",
        "Web Technology", "Artificial Intelligence"
    ],
    "4": [
        "Machine Learning", "Compiler Design", "Cloud Computing",
        "Cyber Security", "Distributed Systems", "Internet of Things",
        "Project / Major Project"
    ],
}

@app.get("/api/batches")
def api_batches():
    if not init_firebase():
        return jsonify({"ok": True, "batches": []})

    docs = db.collection("batches").order_by("year").stream()
    data = []
    for d in docs:
        item = d.to_dict()
        item["id"] = d.id
        data.append(item)
    return jsonify({"ok": True, "batches": data})

@app.get("/api/notes")
def api_notes():
    year = request.args.get("year", "").strip()
    subject = request.args.get("subject", "").strip()
    unit = request.args.get("unit", "").strip()

    if not init_firebase():
        return jsonify({"ok": True, "notes": []})

    ref = db.collection("notes")
    if year:
        ref = ref.where("year", "==", year)
    if subject:
        ref = ref.where("subject", "==", subject)
    if unit:
        ref = ref.where("unit", "==", unit)

    data = []
    for d in ref.stream():
        item = d.to_dict()
        item["id"] = d.id
        data.append(item)

    data.sort(key=lambda x: (str(x.get("year","")), str(x.get("subject","")), str(x.get("unit",""))))
    return jsonify({"ok": True, "notes": data})

@app.get("/download/<path:filename>")
def download(filename):
    # Files are stored only under static/uploads.
    safe_name = Path(filename).name
    path = UPLOAD_DIR / safe_name
    if not path.exists():
        abort(404, description="File not found.")
    return send_from_directory(UPLOAD_DIR, safe_name, as_attachment=True)

# ---------- admin ----------
@app.get("/api/admin/status")
@admin_required
def admin_status():
    return jsonify({"ok": True, "admin": True, "email": ADMIN_EMAIL})

@app.post("/api/admin/batches")
@admin_required
def create_batch():
    payload = request.get_json(silent=True) or {}
    year = str(payload.get("year", "")).strip()
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()

    if year not in {"1", "2", "3", "4"} or not name:
        abort(400, description="Year and batch name are required.")

    ref = db.collection("batches").add({
        "year": year,
        "name": name,
        "description": description,
        "createdBy": ADMIN_EMAIL,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })

    return jsonify({"ok": True, "id": ref[1].id})

@app.post("/api/admin/notes")
@admin_required
def create_note():
    title = request.form.get("title", "").strip()
    year = request.form.get("year", "").strip()
    subject = request.form.get("subject", "").strip()
    unit = request.form.get("unit", "").strip()
    description = request.form.get("description", "").strip()
    file = request.files.get("file")

    if not title or year not in {"1","2","3","4"} or not subject or not unit:
        abort(400, description="Title, year, subject and unit are required.")
    if not file or not file.filename:
        abort(400, description="Select a PDF/file to upload.")

    original = Path(file.filename).name
    ext = Path(original).suffix.lower()
    allowed = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"}
    if ext not in allowed:
        abort(400, description="Allowed files: PDF, DOC, DOCX, PPT, PPTX, TXT.")

    # Unique safe filename
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", original)
    safe = f"{random.randint(100000,999999)}_{safe}"
    file.save(UPLOAD_DIR / safe)

    ref = db.collection("notes").add({
        "title": title,
        "year": year,
        "subject": subject,
        "unit": unit,
        "description": description,
        "filename": safe,
        "originalName": original,
        "createdBy": ADMIN_EMAIL,
        "createdAt": firestore.SERVER_TIMESTAMP,
    })

    return jsonify({"ok": True, "id": ref[1].id})

# ---------- AI ----------
def ai_client():
    if genai is None:
        return None
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None

def generate_ai(prompt):
    client = ai_client()
    if client is None:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model, contents=prompt)
    return (response.text or "").strip()

def fallback_quiz(year, level, exam, subject):
    bank = {
        "Programming for Problem Solving": [
            ("Which data type is commonly used for an integer in C?", ["int", "float", "char", "double"], 0),
            ("Which symbol ends a C statement?", [";", ":", ".", ","], 0),
        ],
        "Data Structures": [
            ("Which structure follows LIFO?", ["Queue", "Stack", "Tree", "Graph"], 1),
            ("Which structure follows FIFO?", ["Stack", "Queue", "Heap", "Tree"], 1),
        ],
        "Operating Systems": [
            ("Which is a process scheduling algorithm?", ["FCFS", "DFS", "BFS", "Dijkstra"], 0),
        ],
        "Database Management Systems": [
            ("Which language is commonly used to query relational databases?", ["HTML", "SQL", "CSS", "C"], 1),
        ],
        "Engineering Mathematics-I": [
            ("The derivative of x² is:", ["x", "2x", "x²", "2"], 1),
        ],
    }
    items = bank.get(subject)
    if not items:
        items = [
            (f"Which statement is most relevant to {subject}?", [
                "A fundamental concept of the subject",
                "A random unrelated fact",
                "A web browser setting",
                "A mobile notification"
            ], 0)
        ]
    random.shuffle(items)
    return [{
        "question": q,
        "options": opts,
        "answer": ans
    } for q, opts, ans in items]

@app.post("/api/ai/quiz")
def ai_quiz():
    payload = request.get_json(silent=True) or {}
    year = str(payload.get("year", "1"))
    level = str(payload.get("level", "Beginner"))
    exam = str(payload.get("exam", "AKTU"))
    subject = str(payload.get("subject", "Programming for Problem Solving"))
    count = min(max(int(payload.get("count", 5)), 3), 10)

    prompt = f"""
You are SamStudy's quiz engine.
Generate exactly {count} multiple-choice questions for:
Class/Year: B.Tech {year} year
Exam: {exam}
Level: {level}
Subject: {subject}

Return ONLY valid JSON as an array.
Each item must have:
question (string),
options (array of exactly 4 strings),
answer (integer 0-3),
explanation (short string).

Questions must be relevant to the selected subject and exam.
Do not repeat generic questions. Vary them each request.
"""
    try:
        text = generate_ai(prompt)
        if text:
            match = re.search(r"\[[\s\S]*\]", text)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return jsonify({"ok": True, "source": "ai", "questions": data})
    except Exception as exc:
        app.logger.warning("AI quiz error: %s", exc)

    return jsonify({
        "ok": True,
        "source": "fallback",
        "questions": fallback_quiz(year, level, exam, subject)
    })

@app.post("/api/ai/doubt")
def ai_doubt():
    payload = request.get_json(silent=True) or {}
    doubt = str(payload.get("doubt", "")).strip()
    context = str(payload.get("context", "")).strip()

    if not doubt:
        abort(400, description="Please enter your doubt.")

    prompt = f"""
You are SamStudy AI Doubt Solver.
Answer the student's doubt clearly and accurately.

Context: {context or "B.Tech / competitive exam study"}
Student doubt:
{doubt}

Rules:
- Start with the direct answer.
- Then explain step-by-step.
- Use formulas/examples when useful.
- If the question is ambiguous, state the assumption.
- Do not invent facts.
- Keep it student-friendly.
"""
    try:
        answer = generate_ai(prompt)
        if answer:
            return jsonify({"ok": True, "answer": answer, "source": "ai"})
    except Exception as exc:
        app.logger.warning("AI doubt error: %s", exc)

    return jsonify({
        "ok": True,
        "source": "fallback",
        "answer": "AI is not configured on this deployment yet. Add GEMINI_API_KEY in Render Environment Variables, then reload SamStudy."
    })

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "firebase_admin": firebase_ready,
        "ai": bool(os.getenv("GEMINI_API_KEY"))
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
