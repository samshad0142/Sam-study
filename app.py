import os
import json
import sqlite3
import uuid
import base64
import hashlib
import re
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


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BASE = Path(__file__).resolve().parent


# ============================================================
# DATABASE
# ============================================================
# You can optionally set:
# SAMSTUDY_DB_PATH=/var/data/samstudy.db
#
# If not set, the app safely uses:
# <project>/data/samstudy.db
#
# The data directory is explicitly created before SQLite opens.

DATA_DIR = BASE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_ENV = os.getenv("SAMSTUDY_DB_PATH", "").strip()

if DB_ENV:
    DB = Path(DB_ENV).expanduser()
else:
    DB = DATA_DIR / "samstudy.db"

DB.parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# UPLOAD DIRECTORIES
# ============================================================

UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

PROFILE_UPLOADS = UPLOADS / "profiles"
PROFILE_UPLOADS.mkdir(parents=True, exist_ok=True)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "dev-secret-change-me"
)


# ============================================================
# ADMIN EMAILS
# ============================================================

ADMIN_EMAILS = {
    x.strip().lower()
    for x in os.getenv(
        "ADMIN_EMAILS",
        os.getenv(
            "ADMIN_EMAIL",
            "samshad0142@gmail.com"
        )
    ).split(",")
    if x.strip()
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db():
    """
    Open SQLite connection safely.

    The parent directory is created again here as an extra
    safety measure so the application cannot fail merely because
    the database directory is missing.
    """

    DB.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(
        str(DB),
        timeout=30
    )

    con.row_factory = sqlite3.Row

    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")

    return con


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    DB.parent.mkdir(parents=True, exist_ok=True)

    with db() as con:

        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                unit TEXT DEFAULT 'All Units',
                title TEXT NOT NULL,
                filename TEXT,
                url TEXT,
                details TEXT DEFAULT '',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(batch_id)
                    REFERENCES batches(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS profiles (
                uid TEXT PRIMARY KEY,
                email TEXT,
                name TEXT DEFAULT '',
                course TEXT DEFAULT '',
                exam TEXT DEFAULT '',
                photo TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS seen_questions (
                uid TEXT NOT NULL,
                qhash TEXT NOT NULL,
                question TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY(uid, qhash)
            );

            CREATE TABLE IF NOT EXISTS test_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL,
                exam TEXT,
                course TEXT,
                subject TEXT,
                score REAL,
                accuracy REAL,
                total INTEGER,
                duration INTEGER,
                answers_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        con.commit()


# ============================================================
# FIREBASE ADMIN INITIALIZATION
# ============================================================

def init_firebase_admin():

    if not firebase_admin:
        print("Firebase Admin SDK is not installed.")
        return

    if firebase_admin._apps:
        return

    raw = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        ""
    ).strip()

    if not raw:
        print(
            "FIREBASE_SERVICE_ACCOUNT_JSON is not configured."
        )
        return

    try:

        service_account = json.loads(raw)

        firebase_admin.initialize_app(
            credentials.Certificate(service_account)
        )

        print("Firebase Admin initialized successfully.")

    except Exception as e:

        print(
            "Firebase Admin initialization failed:",
            e
        )


# ============================================================
# STARTUP
# ============================================================

init_db()
init_firebase_admin()


# ============================================================
# AUTH DECORATOR
# ============================================================

def require_user(admin=False):

    def deco(fn):

        @wraps(fn)
        def wrapped(*args, **kwargs):

            token = request.headers.get(
                "Authorization",
                ""
            )

            if not token.startswith("Bearer "):

                return jsonify(
                    error="Login required."
                ), 401

            if (
                not firebase_admin
                or not firebase_admin._apps
            ):

                return jsonify(
                    error=(
                        "Server Firebase Admin is not configured. "
                        "Add FIREBASE_SERVICE_ACCOUNT_JSON in Render."
                    )
                ), 503

            try:

                decoded = fb_auth.verify_id_token(
                    token[7:].strip()
                )

                email = (
                    decoded.get("email") or ""
                ).lower()

                if admin and email not in ADMIN_EMAILS:

                    return jsonify(
                        error="Developer/admin access required."
                    ), 403

                request.user = decoded

                return fn(*args, **kwargs)

            except Exception as e:

                return jsonify(
                    error=(
                        "Authentication verification failed: "
                        f"{e}"
                    )
                ), 401

        return wrapped

    return deco


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    firebase_config = {

        "apiKey": os.getenv(
            "FIREBASE_API_KEY",
            ""
        ),

        "authDomain": os.getenv(
            "FIREBASE_AUTH_DOMAIN",
            ""
        ),

        "projectId": os.getenv(
            "FIREBASE_PROJECT_ID",
            ""
        ),

        "storageBucket": os.getenv(
            "FIREBASE_STORAGE_BUCKET",
            ""
        ),

        "messagingSenderId": os.getenv(
            "FIREBASE_MESSAGING_SENDER_ID",
            ""
        ),

        "appId": os.getenv(
            "FIREBASE_APP_ID",
            ""
        )
    }

    return render_template(
        "index.html",

        firebase_config=json.dumps(
            firebase_config
        ),

        youtube=os.getenv(
            "YOUTUBE_URL",
            "https://youtube.com/@sam_malik77"
        ),

        admin_emails=sorted(
            ADMIN_EMAILS
        )
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    try:

        with db() as con:
            con.execute(
                "SELECT 1"
            ).fetchone()

        return jsonify(
            ok=True,
            database=True
        )

    except Exception as e:

        return jsonify(
            ok=False,
            database=False,
            error=str(e)
        ), 500


# ============================================================
# BATCHES
# ============================================================

@app.get("/api/batches")
def batches():

    with db() as con:

        rows = con.execute(
            """
            SELECT *
            FROM batches
            ORDER BY year, id DESC
            """
        ).fetchall()

    return jsonify(
        [dict(r) for r in rows]
    )


# ============================================================
# NOTES
# ============================================================

@app.get("/api/notes")
def notes():

    batch_id = request.args.get(
        "batch_id"
    )

    subject = request.args.get(
        "subject"
    )

    query = """
        SELECT
            n.*,
            b.year,
            b.name AS batch_name
        FROM notes n
        JOIN batches b
            ON b.id = n.batch_id
    """

    clauses = []
    params = []

    if batch_id:

        clauses.append(
            "n.batch_id = ?"
        )

        params.append(
            batch_id
        )

    if subject:

        clauses.append(
            "LOWER(n.subject) = LOWER(?)"
        )

        params.append(
            subject
        )

    if clauses:

        query += (
            " WHERE "
            + " AND ".join(clauses)
        )

    query += """
        ORDER BY
            n.subject,
            n.unit,
            n.id DESC
    """

    with db() as con:

        rows = con.execute(
            query,
            params
        ).fetchall()

    return jsonify(
        [dict(r) for r in rows]
    )


# ============================================================
# UPLOADED FILES
# ============================================================

@app.get("/uploads/<path:name>")
def uploaded(name):

    return send_from_directory(
        UPLOADS,
        name,
        as_attachment=True
    )


# ============================================================
# ADMIN - ADD BATCH
# ============================================================

@app.post("/api/admin/batches")
@require_user(admin=True)
def add_batch():

    data = request.get_json(
        force=True
    )

    try:

        year = int(
            data.get(
                "year",
                0
            )
        )

    except Exception:

        year = 0

    name = (
        data.get("name") or ""
    ).strip()

    description = (
        data.get("description") or ""
    ).strip()

    if year not in (1, 2, 3, 4):

        return jsonify(
            error="Year and batch name are required."
        ), 400

    if not name:

        return jsonify(
            error="Year and batch name are required."
        ), 400

    with db() as con:

        cur = con.execute(
            """
            INSERT INTO batches(
                year,
                name,
                description,
                created_by
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                year,
                name,
                description,
                request.user.get(
                    "email"
                )
            )
        )

        con.commit()

        batch_id = cur.lastrowid

    return jsonify(
        ok=True,
        id=batch_id
    )


# ============================================================
# ADMIN - ADD NOTE
# ============================================================

@app.post("/api/admin/notes")
@require_user(admin=True)
def add_note():

    batch_id = request.form.get(
        "batch_id"
    )

    subject = (
        request.form.get(
            "subject",
            ""
        )
    ).strip()

    unit = (
        request.form.get(
            "unit",
            "All Units"
        )
    ).strip()

    title = (
        request.form.get(
            "title",
            ""
        )
    ).strip()

    url = (
        request.form.get(
            "url",
            ""
        )
    ).strip()

    details = (
        request.form.get(
            "details",
            ""
        )
    ).strip()

    if (
        not batch_id
        or not subject
        or not title
    ):

        return jsonify(
            error=(
                "Batch, subject and title "
                "are required."
            )
        ), 400

    filename = None

    file = request.files.get(
        "file"
    )

    if file and file.filename:

        extension = (
            Path(
                file.filename
            ).suffix.lower()
        )

        allowed_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".txt",
            ".zip"
        }

        if extension not in allowed_extensions:

            return jsonify(
                error=(
                    "Use PDF/DOC/PPT/"
                    "TXT/ZIP for notes."
                )
            ), 400

        filename = (
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )

        file.save(
            UPLOADS / filename
        )

    with db() as con:

        con.execute(
            """
            INSERT INTO notes(
                batch_id,
                subject,
                unit,
                title,
                filename,
                url,
                details,
                created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                subject,
                unit,
                title,
                filename,
                url,
                details,
                request.user.get(
                    "email"
                )
            )
        )

        con.commit()

    return jsonify(
        ok=True
    )


# ============================================================
# PROFILE - GET
# ============================================================

@app.get("/api/profile")
@require_user()
def get_profile():

    uid = request.user["uid"]

    with db() as con:

        row = con.execute(
            """
            SELECT *
            FROM profiles
            WHERE uid = ?
            """,
            (uid,)
        ).fetchone()

    verified = bool(
        request.user.get(
            "email_verified"
        )
    )

    email = request.user.get(
        "email",
        ""
    )

    if row:

        return jsonify(
            profile=dict(row),
            email=email,
            verified=verified
        )

    return jsonify(

        profile={
            "uid": uid,

            "email": email,

            "name": request.user.get(
                "name",
                ""
            ),

            "course": "",

            "exam": "",

            "photo": request.user.get(
                "picture",
                ""
            )
        },

        email=email,

        verified=verified
    )


# ============================================================
# PROFILE - SAVE
# ============================================================

@app.post("/api/profile")
@require_user()
def save_profile():

    uid = request.user["uid"]

    email = (
        request.user.get(
            "email"
        ) or ""
    ).lower()

    name = (
        request.form.get(
            "name"
        ) or ""
    ).strip()

    course = (
        request.form.get(
            "course"
        ) or ""
    ).strip()

    exam = (
        request.form.get(
            "exam"
        ) or ""
    ).strip()

    photo = ""

    file = request.files.get(
        "photo"
    )

    if file and file.filename:

        extension = (
            Path(
                file.filename
            ).suffix.lower()
        )

        allowed_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        }

        if extension not in allowed_extensions:

            return jsonify(
                error=(
                    "Profile photo must "
                    "be JPG, PNG or WEBP."
                )
            ), 400

        uid_hash = hashlib.sha256(
            uid.encode()
        ).hexdigest()[:20]

        filename = (
            f"profile_{uid_hash}"
            f"{extension}"
        )

        file.save(
            PROFILE_UPLOADS / filename
        )

        photo = (
            f"/uploads/profiles/{filename}"
        )

    with db() as con:

        old = con.execute(
            """
            SELECT photo
            FROM profiles
            WHERE uid = ?
            """,
            (uid,)
        ).fetchone()

        if not photo and old:

            photo = old["photo"] or ""

        con.execute(
            """
            INSERT INTO profiles(
                uid,
                email,
                name,
                course,
                exam,
                photo
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(uid)
            DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                course = excluded.course,
                exam = excluded.exam,
                photo = excluded.photo,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                uid,
                email,
                name,
                course,
                exam,
                photo
            )
        )

        con.commit()

    return jsonify(

        ok=True,

        profile={
            "uid": uid,
            "email": email,
            "name": name,
            "course": course,
            "exam": exam,
            "photo": photo
        }
    )


# ============================================================
# GEMINI HELPER
# ============================================================

def gemini_parts(parts):

    key = os.getenv(
        "GEMINI_API_KEY",
        ""
    ).strip()

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    ).strip()

    if not key:

        return (
            None,
            "GEMINI_API_KEY is not configured on Render."
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
        f"?key={key}"
    )

    try:

        response = requests.post(

            url,

            json={
                "contents": [
                    {
                        "parts": parts
                    }
                ],

                "generationConfig": {
                    "temperature": 0.35
                }
            },

            timeout=60
        )

        if response.status_code != 200:

            try:

                error_data = response.json()

                message = (
                    error_data
                    .get("error", {})
                    .get("message")
                )

            except Exception:

                message = None

            return (
                None,
                (
                    f"AI service error "
                    f"({response.status_code})"
                    + (
                        f": {message}"
                        if message
                        else "."
                    )
                )
            )

        data = response.json()

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:

            return (
                None,
                "AI returned no answer."
            )

        content = candidates[0].get(
            "content",
            {}
        )

        parts_out = content.get(
            "parts",
            []
        )

        text_parts = []

        for item in parts_out:

            if item.get("text"):

                text_parts.append(
                    item["text"]
                )

        text = "\n".join(
            text_parts
        ).strip()

        if not text:

            return (
                None,
                "AI returned an empty answer."
            )

        return text, None

    except requests.RequestException as e:

        return (
            None,
            f"AI network error: {e}"
        )

    except Exception as e:

        return (
            None,
            str(e)
        )


# ============================================================
# AI DOUBT SOLVER
# ============================================================

@app.post("/api/ai/doubt")
def ai_doubt():

    data = request.get_json(
        force=True
    )

    doubt = (
        data.get("doubt") or ""
    ).strip()

    image_data = data.get(
        "image"
    )

    if not doubt and not image_data:

        return jsonify(
            error=(
                "Type a doubt or "
                "upload an image."
            )
        ), 400

    prompt = """
You are SamStudy AI.

Solve the student's academic doubt accurately.

Give:
1. A clear explanation.
2. Step-by-step solution.
3. Relevant formulas/calculations.
4. Final answer.

If an image is supplied, carefully read the problem from it.

Do not invent information.
If the question is unclear, clearly say what is unclear.
"""

    parts = [

        {
            "text":
                prompt
                + "\nStudent text: "
                + (
                    doubt
                    or "(image only)"
                )
        }

    ]

    if image_data and "," in image_data:

        header, encoded = (
            image_data.split(
                ",",
                1
            )
        )

        mime_match = re.search(
            r"data:(.*?);base64",
            header
        )

        if mime_match:

            parts.append(

                {
                    "inline_data": {
                        "mime_type":
                            mime_match.group(1),

                        "data":
                            encoded
                    }
                }

            )

    text, error = gemini_parts(
        parts
    )

    if error:

        return jsonify(
            error=error
        ), 503

    return jsonify(
        answer=text
    )


# ============================================================
# SEEN QUESTIONS
# ============================================================

def seen_for(uid):

    with db() as con:

        rows = con.execute(
            """
            SELECT question
            FROM seen_questions
            WHERE uid = ?
            ORDER BY created_at DESC
            LIMIT 250
            """,
            (uid,)
        ).fetchall()

    return [
        row["question"]
        for row in rows
    ]


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(text):

    cleaned = (
        text or ""
    ).strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.I
    ).strip()

    return json.loads(
        cleaned
    )


# ============================================================
# AI QUIZ
# ============================================================

@app.post("/api/ai/quiz")
@require_user()
def ai_quiz():

    data = request.get_json(
        force=True
    )

    course = (
        data.get("course")
        or "B.Tech"
    )

    exam = (
        data.get("exam")
        or "JEE Main"
    )

    subject = (
        data.get("subject")
        or "General"
    )

    try:

        count = int(
            data.get(
                "count",
                10
            )
        )

    except Exception:

        count = 10

    count = max(
        1,
        min(count, 50)
    )

    difficulty = (
        data.get("difficulty")
        or "Mixed"
    )

    uid = request.user["uid"]

    seen = seen_for(uid)

    avoid = "\n".join(
        f"- {question}"
        for question in seen[-120:]
    )

    prompt = f"""
Create {count} high-quality MCQs for {course} students preparing for {exam}.

Subject: {subject}
Difficulty: {difficulty}

Prioritize:
- Official/known PYQ concepts
- Real exam pattern
- Relevant syllabus
- Conceptual accuracy

You may include PYQ-style questions.

Do not falsely attribute a question to a specific year unless certain.

Avoid repeating questions from the previous-question list.

Return ONLY a JSON array.

Each item must be:

{{
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "answer": 0,
  "explanation": "Detailed solution",
  "source": "PYQ / PYQ-style / Original"
}}

The answer must be a zero-based option index.

Previously seen questions:

{avoid or "(none)"}
"""

    text, error = gemini_parts(
        [
            {
                "text": prompt
            }
        ]
    )

    if error:

        return jsonify(
            error=error
        ), 503

    try:

        questions = parse_json(
            text
        )

        cleaned = []

        local_hashes = set()

        with db() as con:

            for question in questions:

                question["question"] = str(
                    question.get(
                        "question",
                        ""
                    )
                ).strip()

                question["options"] = (
                    question.get(
                        "options",
                        []
                    )[:4]
                )

                if (
                    len(
                        question["options"]
                    ) != 4
                    or not question["question"]
                ):

                    continue

                try:

                    question["answer"] = int(
                        question.get(
                            "answer",
                            0
                        )
                    )

                except Exception:

                    continue

                if question["answer"] not in range(4):

                    continue

                question["explanation"] = str(
                    question.get(
                        "explanation",
                        ""
                    )
                )

                question["source"] = str(
                    question.get(
                        "source",
                        "AI"
                    )
                )

                question_hash = hashlib.sha256(
                    question[
                        "question"
                    ].strip().lower().encode()
                ).hexdigest()

                if question_hash in local_hashes:

                    continue

                already_seen = con.execute(
                    """
                    SELECT 1
                    FROM seen_questions
                    WHERE uid = ?
                      AND qhash = ?
                    """,
                    (
                        uid,
                        question_hash
                    )
                ).fetchone()

                if already_seen:

                    continue

                local_hashes.add(
                    question_hash
                )

                con.execute(
                    """
                    INSERT INTO seen_questions(
                        uid,
                        qhash,
                        question
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        uid,
                        question_hash,
                        question["question"]
                    )
                )

                cleaned.append(
                    question
                )

                if len(cleaned) >= count:

                    break

            con.commit()

        return jsonify(
            questions=cleaned
        )

    except Exception as e:

        print(
            "Quiz parsing error:",
            e
        )

        return jsonify(
            error=(
                "AI returned an invalid "
                "quiz format. Please try again."
            )
        ), 502


# ============================================================
# AI TEST GENERATOR
# ============================================================

@app.post("/api/ai/test")
@require_user()
def ai_test():

    data = request.get_json(
        force=True
    )

    course = (
        data.get("course")
        or "B.Tech"
    )

    exam = (
        data.get("exam")
        or "JEE Main"
    )

    subject = (
        data.get("subject")
        or "General"
    )

    try:

        count = int(
            data.get(
                "count",
                20
            )
        )

    except Exception:

        count = 20

    count = max(
        5,
        min(count, 100)
    )

    difficulty = (
        data.get("difficulty")
        or "Real exam"
    )

    prompt = f"""
Create a realistic {exam} practice test
for {course}.

Subject:
{subject}

Question count:
{count}

Level:
{difficulty}

Mimic the real exam's:
- Question style
- Difficulty
- Options
- Marking concept
- Syllabus focus

Prefer PYQ concepts and original questions.

Do not reproduce copyrighted material verbatim.

Return ONLY JSON array.

Each object must contain:

{{
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "answer": 0,
  "explanation": "Detailed solution",
  "marks": 1,
  "negative": 0,
  "level": "Easy|Medium|Hard"
}}
"""

    text, error = gemini_parts(
        [
            {
                "text": prompt
            }
        ]
    )

    if error:

        return jsonify(
            error=error
        ), 503

    try:

        questions = parse_json(
            text
        )

        return jsonify(
            questions=questions[:count]
        )

    except Exception:

        return jsonify(
            error=(
                "AI returned an invalid "
                "test format. Please try again."
            )
        ), 502


# ============================================================
# TEST SUBMISSION
# ============================================================

@app.post("/api/test/submit")
@require_user()
def submit_test():

    data = request.get_json(
        force=True
    )

    questions = data.get(
        "questions",
        []
    )

    answers = data.get(
        "answers",
        {}
    )

    try:

        duration = int(
            data.get(
                "duration",
                0
            )
        )

    except Exception:

        duration = 0

    score = 0.0
    maxmarks = 0.0
    correct = 0

    results = []

    for index, question in enumerate(
        questions
    ):

        try:

            marks = float(
                question.get(
                    "marks",
                    1
                )
            )

        except Exception:

            marks = 1.0

        try:

            negative = float(
                question.get(
                    "negative",
                    0
                )
            )

        except Exception:

            negative = 0.0

        maxmarks += marks

        selected = answers.get(
            str(index)
        )

        try:

            is_correct = (
                selected is not None
                and int(selected)
                == int(
                    question.get(
                        "answer",
                        0
                    )
                )
            )

        except Exception:

            is_correct = False

        if is_correct:

            score += marks
            correct += 1

        elif selected is not None:

            score -= negative

        results.append(

            {
                "correct":
                    is_correct,

                "selected":
                    selected,

                "answer":
                    question.get(
                        "answer"
                    ),

                "explanation":
                    question.get(
                        "explanation",
                        ""
                    ),

                "level":
                    question.get(
                        "level",
                        ""
                    ),

                "marks":
                    marks,

                "negative":
                    negative
            }

        )

    total = len(
        questions
    )

    accuracy = (
        correct / total * 100
        if total
        else 0
    )

    with db() as con:

        con.execute(
            """
            INSERT INTO test_attempts(
                uid,
                exam,
                course,
                subject,
                score,
                accuracy,
                total,
                duration,
                answers_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.user["uid"],

                data.get(
                    "exam"
                ),

                data.get(
                    "course"
                ),

                data.get(
                    "subject"
                ),

                score,

                accuracy,

                total,

                duration,

                json.dumps(
                    results
                )
            )
        )

        con.commit()

    return jsonify(

        score=score,

        max_marks=maxmarks,

        accuracy=accuracy,

        total=total,

        duration=duration,

        results=results
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        )
    )
