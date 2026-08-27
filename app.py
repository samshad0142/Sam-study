import os
import json
import re
import sqlite3
import base64
import secrets
import hmac
import hashlib
import time

from pathlib import Path
from functools import wraps
from datetime import datetime
from urllib.parse import quote_plus

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    abort,
    session,
)


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent

DATA = ROOT / "data"
STATIC = ROOT / "static"
TEMPLATES = ROOT / "templates"

UPLOADS = DATA / "uploads"
BOOKS = UPLOADS / "books"
CONTENT = UPLOADS / "content"
GENERATED = DATA / "generated"

for folder in (
    DATA,
    UPLOADS,
    BOOKS,
    CONTENT,
    GENERATED,
):
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATES),
    static_folder=str(STATIC),
    static_url_path="/static",
)

# IMPORTANT:
# Gunicorn must be able to find this object as app:app.
application = app

app.secret_key = (
    os.getenv("SECRET_KEY")
    or secrets.token_hex(32)
)

app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ============================================================
# ENVIRONMENT
# ============================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "samshad0142@gmail.com",
).strip().lower()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "",
).strip()

GEMINI_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.7-flash",
).strip()

YOUTUBE_URL = os.getenv(
    "YOUTUBE_URL",
    "https://www.youtube.com/@Sam_malik77",
).strip()

INSTAGRAM_URL = os.getenv(
    "INSTAGRAM_URL",
    "https://www.instagram.com/Sam_shad132/",
).strip()


# ============================================================
# DATABASE / JSON
# ============================================================

DB = DATA / "samstudy.db"

CHANGES = DATA / "changes.json"
CATALOG_FILE = DATA / "catalog.json"
CHAPTERS_FILE = DATA / "chapters.json"

if not CHANGES.exists():
    CHANGES.write_text("[]", encoding="utf-8")


def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


CATALOG = load_json(
    CATALOG_FILE,
    {
        "exams": {},
        "courses": {},
    },
)

CHAPTERS = load_json(
    CHAPTERS_FILE,
    {},
)


def db():
    con = sqlite3.connect(
        DB,
        timeout=20,
    )
    con.row_factory = sqlite3.Row
    return con


# ============================================================
# PASSWORD
# ============================================================

def password_hash(password):
    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        180000,
    )

    return (
        salt.hex()
        + "$"
        + digest.hex()
    )


def password_ok(password, stored):
    try:
        salt_hex, digest_hex = stored.split(
            "$",
            1,
        )

        got = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            180000,
        ).hex()

        return hmac.compare_digest(
            got,
            digest_hex,
        )

    except Exception:
        return False


# ============================================================
# DATABASE INIT
# ============================================================

def init_db():

    con = db()

    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS progress(
            uid TEXT NOT NULL,
            resource TEXT NOT NULL,
            value REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(uid, resource)
        );

        CREATE TABLE IF NOT EXISTS shield_rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            app_name TEXT NOT NULL,
            minutes INTEGER NOT NULL DEFAULT 60,
            reset_time TEXT NOT NULL DEFAULT '00:00',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )

    if ADMIN_PASSWORD:

        row = con.execute(
            "SELECT id FROM users WHERE email=?",
            (ADMIN_EMAIL,),
        ).fetchone()

        if not row:

            con.execute(
                """
                INSERT INTO users(
                    email,
                    password_hash,
                    name,
                    created_at
                )
                VALUES(?,?,?,?)
                """,
                (
                    ADMIN_EMAIL,
                    password_hash(
                        ADMIN_PASSWORD
                    ),
                    "SamStudy Developer",
                    datetime.utcnow().isoformat(),
                ),
            )

            con.commit()

    con.close()


init_db()


# ============================================================
# AUTH
# ============================================================

def current_local_user():

    uid = session.get("uid")

    if not uid:
        return None

    con = db()

    row = con.execute(
        """
        SELECT id,email,name
        FROM users
        WHERE id=?
        """,
        (uid,),
    ).fetchone()

    con.close()

    if not row:
        return None

    return {
        "uid": str(row["id"]),
        "email": row["email"],
        "name": row["name"] or "",
        "emailVerified": True,
        "local": True,
    }


def firebase_user_from_token(token):

    if not token:
        return None

    try:

        import firebase_admin

        from firebase_admin import (
            credentials,
            auth,
        )

        if not firebase_admin._apps:

            raw_b64 = os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_JSON_B64",
                "",
            ).strip()

            raw_json = os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_JSON",
                "",
            ).strip()

            if raw_b64:

                info = json.loads(
                    base64.b64decode(
                        raw_b64
                    ).decode("utf-8")
                )

                firebase_admin.initialize_app(
                    credentials.Certificate(info)
                )

            elif raw_json:

                firebase_admin.initialize_app(
                    credentials.Certificate(
                        json.loads(raw_json)
                    )
                )

            else:
                return None

        user = auth.verify_id_token(token)

        return {
            "uid": user.get("uid"),
            "email": (
                user.get("email") or ""
            ).lower(),
            "name": user.get("name") or "",
            "emailVerified": bool(
                user.get("email_verified")
            ),
        }

    except Exception:
        return None


def request_user():

    authz = request.headers.get(
        "Authorization",
        "",
    )

    if authz.startswith("Bearer "):

        user = firebase_user_from_token(
            authz[7:]
        )

        if user:
            return user

    return current_local_user()


def require_user(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if not request_user():

            return jsonify(
                error="Login required"
            ), 401

        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        user = request_user()

        if (
            not user
            or (
                user.get("email") or ""
            ).lower()
            != ADMIN_EMAIL
        ):

            return jsonify(
                error=(
                    "Developer access required. "
                    "Sign in with the configured "
                    "admin account."
                )
            ), 403

        return fn(*args, **kwargs)

    return wrapper


# ============================================================
# GEMINI
# ============================================================

def gemini(
    prompt,
    *,
    image_bytes=None,
    image_mime="image/jpeg",
    json_mode=False,
    grounded=False,
    thinking_level="medium",
):

    if not GEMINI_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured "
            "in Render Environment Variables."
        )

    import requests

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    parts = [
        {
            "text": prompt
        }
    ]

    if image_bytes:

        parts.append(
            {
                "inlineData": {
                    "mimeType": image_mime,
                    "data": base64.b64encode(
                        image_bytes
                    ).decode("ascii"),
                }
            }
        )

    generation_config = {}

    if thinking_level:

        generation_config[
            "thinkingConfig"
        ] = {
            "thinkingLevel": thinking_level
        }

    if json_mode:

        generation_config[
            "responseMimeType"
        ] = "application/json"

    body = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": generation_config,
    }

    # IMPORTANT:
    # Gemini REST API uses googleSearch.
    if grounded:

        body["tools"] = [
            {
                "googleSearch": {}
            }
        ]

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_KEY,
    }

    last_error = None

    for attempt in range(3):

        try:

            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=180,
            )

            if response.ok:

                data = response.json()

                candidates = (
                    data.get("candidates")
                    or []
                )

                if not candidates:
                    raise RuntimeError(
                        "Gemini returned no candidates."
                    )

                content = (
                    candidates[0].get(
                        "content"
                    )
                    or {}
                )

                output_parts = (
                    content.get("parts")
                    or []
                )

                text_parts = [
                    part.get("text", "")
                    for part in output_parts
                    if part.get("text")
                ]

                if not text_parts:
                    raise RuntimeError(
                        "Gemini returned no usable answer."
                    )

                return (
                    "\n".join(text_parts),
                    data,
                )

            last_error = (
                f"Gemini API error "
                f"{response.status_code}: "
                f"{response.text[:2000]}"
            )

            if response.status_code not in (
                429,
                500,
                502,
                503,
                504,
            ):
                break

            if attempt < 2:
                time.sleep(
                    2 ** attempt
                )

        except Exception as exc:

            last_error = str(exc)

            if attempt < 2:
                time.sleep(
                    2 ** attempt
                )

    raise RuntimeError(
        last_error
        or "Gemini request failed."
    )


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(text):

    text = (
        text or ""
    ).strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return json.loads(
        text.strip()
    )


# ============================================================
# QUESTION ALLOCATION
# ============================================================

def allocation(
    n,
    pattern=None,
):

    composition = (
        (pattern or {})
        .get("composition")
        or {}
    )

    total = sum(
        int(
            composition.get(
                key,
                0,
            )
        )
        for key in (
            "pyq",
            "typed",
            "hard",
        )
    )

    if (
        composition
        and total == n
    ):

        return (
            int(
                composition.get(
                    "pyq",
                    0,
                )
            ),
            int(
                composition.get(
                    "typed",
                    0,
                )
            ),
            int(
                composition.get(
                    "hard",
                    0,
                )
            ),
        )

    pyq = round(
        n * 0.60
    )

    typed = round(
        n * 0.30
    )

    hard = n - pyq - typed

    return (
        pyq,
        typed,
        max(0, hard),
    )


# ============================================================
# FALLBACK QUESTIONS
# ============================================================

DEFAULT_QUESTIONS = [

    {
        "question": (
            "If a number is increased by 20%, "
            "the result is 240. "
            "What was the original number?"
        ),
        "options": [
            "180",
            "200",
            "220",
            "210",
        ],
        "answer": 1,
        "explanation": (
            "Let the original number be x. "
            "Then 1.2x = 240, so x = 200."
        ),
        "subject": "Quantitative Aptitude",
    },

    {
        "question": (
            "Which data structure follows "
            "the FIFO principle?"
        ),
        "options": [
            "Stack",
            "Queue",
            "Tree",
            "Graph",
        ],
        "answer": 1,
        "explanation": (
            "FIFO means First In, First Out, "
            "which is the defining behavior "
            "of a queue."
        ),
        "subject": "Data Structures",
    },

    {
        "question": (
            "What is the derivative of x²?"
        ),
        "options": [
            "x",
            "2x",
            "x²",
            "2",
        ],
        "answer": 1,
        "explanation": (
            "Using the power rule, "
            "d(x²)/dx = 2x."
        ),
        "subject": "Mathematics",
    },

    {
        "question": (
            "What is the most abundant gas "
            "in Earth's atmosphere?"
        ),
        "options": [
            "Oxygen",
            "Nitrogen",
            "Carbon dioxide",
            "Hydrogen",
        ],
        "answer": 1,
        "explanation": (
            "Nitrogen makes up about 78% "
            "of Earth's dry atmosphere."
        ),
        "subject": "General Awareness",
    },

    {
        "question": (
            "Solve: x² − 5x + 6 = 0."
        ),
        "options": [
            "x = 1, 6",
            "x = 2, 3",
            "x = −2, −3",
            "x = 0, 5",
        ],
        "answer": 1,
        "explanation": (
            "Factor: "
            "(x − 2)(x − 3) = 0, "
            "so x = 2 or 3."
        ),
        "subject": "Mathematics",
    },

]


def fallback_questions(
    n,
    exam,
    etype,
    subjects,
):

    result = []

    for i in range(n):

        question = dict(
            DEFAULT_QUESTIONS[
                i % len(DEFAULT_QUESTIONS)
            ]
        )

        question["options"] = list(
            question["options"]
        )

        question["sourceType"] = (
            "PYQ-type"
        )

        question["source"] = (
            "SamStudy fallback practice"
        )

        if subjects:

            question["subject"] = (
                subjects[
                    i % len(subjects)
                ]
            )

        result.append(question)

    return result


# ============================================================
# PAGES
# ============================================================

@app.get("/")
def home():

    return render_template(
        "index.html",
        initial_page="home",
    )


@app.get("/preview")
def preview():

    return render_template(
        "index.html",
        initial_page="home",
    )


@app.get("/health")
def health():

    return jsonify(
        ok=True,
        ai=bool(GEMINI_KEY),
        localLogin=True,
        firebase=bool(
            os.getenv(
                "FIREBASE_API_KEY"
            )
        ),
        model=GEMINI_MODEL,
    )


@app.get("/<page>")
def page_alias(page):

    targets = {
        "login": "profile",
        "signup": "profile",
        "test": "test",
        "tests": "test",
        "doubt": "ai",
        "three-d": "three",
        "notes": "resource",
        "resource": "resource",
        "studyshield": "shield",
        "shield": "shield",
        "ai": "ai",
    }

    allowed = {
        "batches",
        "subjects",
        "quiz",
        "profile",
        "admin",
    }

    if (
        page in targets
        or page in allowed
    ):

        return render_template(
            "index.html",
            initial_page=targets.get(
                page,
                page,
            ),
        )

    abort(404)


@app.get("/manifest.webmanifest")
def manifest():

    return send_from_directory(
        ROOT,
        "manifest.webmanifest",
    )


# ============================================================
# AUTH API
# ============================================================

@app.post("/api/auth/register")
def register():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    email = str(
        data.get(
            "email",
            "",
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            "",
        )
    )

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    if (
        not email
        or "@" not in email
        or len(password) < 6
    ):

        return jsonify(
            error=(
                "Enter a valid email and "
                "a password of at least "
                "6 characters."
            )
        ), 400

    if (
        email == ADMIN_EMAIL
        and ADMIN_PASSWORD
        and password != ADMIN_PASSWORD
    ):

        return jsonify(
            error=(
                "This email is reserved for "
                "the SamStudy developer account."
            )
        ), 403

    con = db()

    try:

        cursor = con.execute(
            """
            INSERT INTO users(
                email,
                password_hash,
                name,
                created_at
            )
            VALUES(?,?,?,?)
            """,
            (
                email,
                password_hash(password),
                name,
                datetime.utcnow().isoformat(),
            ),
        )

        con.commit()

        uid = cursor.lastrowid

    except sqlite3.IntegrityError:

        con.close()

        return jsonify(
            error=(
                "An account with this "
                "email already exists."
            )
        ), 409

    con.close()

    session["uid"] = uid

    return jsonify(
        user={
            "uid": str(uid),
            "email": email,
            "name": name,
            "emailVerified": True,
            "local": True,
        }
    )


@app.post("/api/auth/login")
def login_local():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    email = str(
        data.get(
            "email",
            "",
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            "",
        )
    )

    con = db()

    row = con.execute(
        """
        SELECT
            id,
            email,
            password_hash,
            name
        FROM users
        WHERE email=?
        """,
        (email,),
    ).fetchone()

    con.close()

    if (
        not row
        or not password_ok(
            password,
            row["password_hash"],
        )
    ):

        return jsonify(
            error="Invalid email or password."
        ), 401

    session["uid"] = row["id"]

    return jsonify(
        user={
            "uid": str(row["id"]),
            "email": row["email"],
            "name": row["name"] or "",
            "emailVerified": True,
            "local": True,
        }
    )


@app.post("/api/auth/logout")
def logout_local():

    session.clear()

    return jsonify(
        ok=True
    )


@app.get("/api/auth/me")
def auth_me():

    return jsonify(
        user=request_user()
    )


# ============================================================
# CONFIG
# ============================================================

@app.get("/api/config")
def config():

    firebase = {

        "apiKey": os.getenv(
            "FIREBASE_API_KEY",
            "",
        ).strip(),

        "authDomain": os.getenv(
            "FIREBASE_AUTH_DOMAIN",
            "",
        ).strip(),

        "projectId": os.getenv(
            "FIREBASE_PROJECT_ID",
            "",
        ).strip(),

        "storageBucket": os.getenv(
            "FIREBASE_STORAGE_BUCKET",
            "",
        ).strip(),

        "messagingSenderId": os.getenv(
            "FIREBASE_MESSAGING_SENDER_ID",
            "",
        ).strip(),

        "appId": os.getenv(
            "FIREBASE_APP_ID",
            "",
        ).strip(),
    }

    return jsonify(

        firebase=firebase,

        firebaseConfigured=all(
            firebase.values()
        ),

        adminEmail=ADMIN_EMAIL,

        geminiConfigured=bool(
            GEMINI_KEY
        ),

        geminiModel=GEMINI_MODEL,

        youtube=YOUTUBE_URL,

        instagram=INSTAGRAM_URL,

        localLogin=True,
    )


# ============================================================
# CATALOG / RESOURCES
# ============================================================

@app.get("/api/catalog")
def catalog():

    return jsonify(
        CATALOG
    )


@app.get("/api/chapters")
def chapters():

    subject = (
        request.args.get(
            "subject"
        )
        or ""
    ).strip()

    fallback = [
        "Introduction",
        "Core Concepts",
        "Important Definitions",
        "Key Formulas / Rules",
        "Solved Examples",
        "Common Mistakes",
        "Practice Questions",
        "Revision",
    ]

    return jsonify(
        subject=subject,
        chapters=CHAPTERS.get(
            subject,
            fallback,
        ),
    )


def changes():

    return load_json(
        CHANGES,
        [],
    )


def save_changes(data):

    CHANGES.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@app.get("/api/catalog-changes")
def catalog_changes():

    return jsonify(
        changes()
    )


@app.get("/api/resources")
def resources():

    result = changes()

    uploaded = []

    for path in CONTENT.rglob("*"):

        if not path.is_file():
            continue

        relative = str(
            path.relative_to(
                CONTENT
            )
        ).replace(
            "\\",
            "/",
        )

        uploaded.append(
            {
                "kind": "resource",
                "resourceKind": "Notes",
                "subject": "",
                "name": path.name,
                "url": (
                    "/content/"
                    + quote_plus(
                        relative
                    ).replace(
                        "%2F",
                        "/",
                    )
                ),
            }
        )

    return jsonify(
        result + uploaded
    )


@app.get("/content/<path:name>")
def content(name):

    return send_from_directory(
        CONTENT,
        name,
        as_attachment=False,
    )


@app.get("/books/<path:name>")
def books(name):

    return send_from_directory(
        BOOKS,
        name,
        as_attachment=False,
    )


# ============================================================
# AI QUIZ / TEST
# ============================================================

@app.post("/api/ai/quiz")
def ai_quiz():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    mode = str(
        data.get(
            "mode",
            "quiz",
        )
    )

    try:
        count = int(
            data.get(
                "count",
                10,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        count = 10

    count = max(
        1,
        min(
            count,
            200,
        ),
    )

    exam = str(
        data.get(
            "exam",
            "SSC",
        )
    )

    exam_type = str(
        data.get(
            "type",
            "",
        )
    )

    subjects = (
        data.get(
            "subjects"
        )
        or []
    )

    pattern = (
        data.get(
            "pattern"
        )
        or {}
    )

    pyq, typed, hard = allocation(
        count,
        pattern
        if mode == "test"
        else None,
    )

    composition = (
        f"exactly {pyq} PYQ, "
        f"{typed} PYQ-type, "
        f"{hard} HARDEST"
    )

    prompt = f"""
You are SamStudy's exam engine.

Create exactly {count} MCQs.

Exam:
{exam}

Exam type:
{exam_type}

Subjects:
{", ".join(map(str, subjects)) or "mixed"}

Composition:
{composition}

For every question return:

question
options
answer
explanation
subject
sourceType
source

Rules:

1. options must contain exactly 4 choices.

2. answer must be an integer from 0 to 3.

3. Use sourceType "PYQ" only when the
past question can be confidently verified.

4. Otherwise use "PYQ-type".

5. Never invent a PYQ citation.

6. Keep explanations educational.

7. Return JSON array only.

Test pattern:
{json.dumps(pattern, ensure_ascii=False)}
"""

    try:

        text, _ = gemini(
            prompt,
            json_mode=True,
            grounded=True,
        )

        questions = parse_json(
            text
        )

        if not isinstance(
            questions,
            list,
        ):
            raise ValueError(
                "Gemini returned invalid question JSON."
            )

        cleaned = []

        for item in questions:

            if not isinstance(
                item,
                dict,
            ):
                continue

            options = (
                item.get(
                    "options"
                )
                or []
            )

            if (
                not item.get(
                    "question"
                )
                or len(options) != 4
            ):
                continue

            item["options"] = [
                str(option)
                for option in options
            ]

            try:

                answer = int(
                    item.get(
                        "answer",
                        0,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                answer = 0

            item["answer"] = max(
                0,
                min(
                    3,
                    answer,
                ),
            )

            cleaned.append(
                item
            )

        if len(cleaned) < count:

            raise ValueError(
                "Gemini returned fewer valid "
                "questions than requested."
            )

        return jsonify(
            questions=cleaned[:count],
            source="Gemini",
        )

    except Exception as exc:

        return jsonify(
            questions=fallback_questions(
                count,
                exam,
                exam_type,
                subjects,
            ),
            source="Offline safe bank",
            warning=str(exc),
        )


@app.post("/api/quiz")
def quiz_alias():

    return ai_quiz()


# ============================================================
# AI DOUBT
# ============================================================

@app.post("/api/ai/doubt")
def ai_doubt():

    question = ""
    image = None
    mime = "image/jpeg"
    track = ""

    if request.files:

        question = (
            request.form.get(
                "question",
                "",
            )
            .strip()
        )

        track = (
            request.form.get(
                "track",
                "",
            )
            .strip()
        )

        uploaded = request.files.get(
            "image"
        )

        if uploaded:

            image = uploaded.read()

            mime = (
                uploaded.mimetype
                or mime
            )

    else:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        question = str(
            data.get(
                "question",
                "",
            )
        ).strip()

        track = str(
            data.get(
                "track",
                "",
            )
        ).strip()

        image_data = (
            data.get(
                "image"
            )
            or {}
        )

        if image_data.get("data"):

            try:

                image = base64.b64decode(
                    image_data["data"]
                )

                mime = (
                    image_data.get(
                        "mimeType"
                    )
                    or mime
                )

            except Exception:

                image = None

    if (
        not question
        and not image
    ):

        return jsonify(
            error=(
                "Enter a doubt or "
                "attach a photo."
            )
        ), 400

    prompt = f"""
You are SamStudy AI tutor.

Solve the student's doubt
step by step.

Student track:
{track or "Not specified"}

Use proper mathematical notation
such as x², √, ≤, ≥, ∑ or LaTeX.

Do not add decorative symbols.

If a fact depends on a source,
say what should be verified.

Question:

{question or "Solve the attached image."}
"""

    try:

        text, _ = gemini(
            prompt,
            image_bytes=image,
            image_mime=mime,
            grounded=True,
        )

        return jsonify(
            answer=text,
            source="Gemini",
        )

    except Exception as exc:

        return jsonify(
            answer=(
                "Gemini could not answer "
                "this request right now."
            ),
            source="Gemini",
            warning=str(exc),
        )


# ============================================================
# AI 3D
# ============================================================

@app.post("/api/ai/3d")
def ai_3d():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    concept = str(
        data.get(
            "concept",
            "",
        )
    ).strip()

    if not concept:

        return jsonify(
            error="Enter a concept."
        ), 400

    prompt = f"""
Create a concise educational
3D scene for the concept:

"{concept}"

Return JSON containing:

title
explanation
objects

Each object must contain:

type
x
y
z
scale
color
label

Allowed types:

box
sphere
cylinder
torus
plane
arrow

Maximum 12 objects.

The scene should visually explain
the concept, not merely decorate it.
"""

    try:

        text, _ = gemini(
            prompt,
            json_mode=True,
        )

        scene = parse_json(
            text
        )

        return jsonify(
            title=scene.get(
                "title",
                concept,
            ),
            explanation=scene.get(
                "explanation",
                "",
            ),
            scene=scene,
            source="Gemini",
        )

    except Exception as exc:

        return jsonify(
            title=concept,
            explanation=(
                "Interactive fallback scene. "
                "Add GEMINI_API_KEY for "
                "concept-specific generation."
            ),
            scene={
                "objects": [
                    {
                        "type": "sphere",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                        "scale": 1.2,
                        "color": "#168cff",
                        "label": concept,
                    },
                    {
                        "type": "arrow",
                        "x": 0,
                        "y": 1.6,
                        "z": 0,
                        "scale": 1,
                        "color": "#ffd166",
                        "label": "Direction",
                    },
                ]
            },
            source="Fallback",
            warning=str(exc),
        )


# ============================================================
# AI NOTES
# ============================================================

@app.post("/api/ai/notes")
def ai_notes():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    subject = str(
        data.get(
            "subject",
            "",
        )
    ).strip()

    chapter = str(
        data.get(
            "chapter",
            "",
        )
    ).strip()

    exam = str(
        data.get(
            "exam",
            "",
        )
    )

    exam_type = str(
        data.get(
            "type",
            "",
        )
    )

    if (
        not subject
        or not chapter
    ):

        return jsonify(
            error=(
                "Subject and chapter "
                "are required."
            )
        ), 400

    prompt = f"""
Create structured study notes.

Exam:
{exam}

Exam type:
{exam_type}

Subject:
{subject}

Chapter:
{chapter}

Include:

headings
definitions
formulas
solved examples
common mistakes
quick revision

Mathematical expressions must use
clean LaTeX or Unicode.

Do not use decorative symbols.

If source verification is requested,
distinguish textbook knowledge from
verified sources.
"""

    try:

        text, _ = gemini(
            prompt,
            grounded=True,
        )

        source = "Gemini"

    except Exception as exc:

        text = (
            f"{chapter}\n\n"
            "Key concepts\n"
            "- Review the core definitions "
            "and formulas for this chapter.\n"
            "- Add examples from your "
            "prescribed textbook.\n\n"
            f"AI status: {exc}"
        )

        source = "Fallback"

    try:

        from reportlab.lib.pagesizes import A4

        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
        )

        from reportlab.lib.styles import (
            getSampleStyleSheet,
        )

        filename = (
            "notes_"
            + secrets.token_hex(8)
            + ".pdf"
        )

        path = (
            GENERATED
            / filename
        )

        document = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        )

        styles = (
            getSampleStyleSheet()
        )

        story = [
            Paragraph(
                "SamStudy — Chapter Notes",
                styles["Title"],
            ),
            Spacer(1, 12),
            Paragraph(
                f"{subject} — {chapter}",
                styles["Heading2"],
            ),
            Spacer(1, 8),
        ]

        blocks = re.split(
            r"\n\s*\n",
            text,
        )

        for block in blocks:

            clean = re.sub(
                r"[<>]",
                "",
                block,
            )

            clean = (
                clean
                .replace(
                    "&",
                    "&amp;",
                )
                .replace(
                    "\n",
                    "<br/>",
                )
            )

            story.append(
                Paragraph(
                    clean,
                    styles["BodyText"],
                )
            )

            story.append(
                Spacer(
                    1,
                    8,
                )
            )

        document.build(story)

        return jsonify(
            download=(
                "/generated/"
                + filename
            ),
            text=text,
            source=source,
        )

    except Exception as exc:

        return jsonify(
            error=(
                "PDF generation failed: "
                f"{exc}"
            )
        ), 500


@app.get("/generated/<path:name>")
def generated(name):

    return send_from_directory(
        GENERATED,
        name,
        as_attachment=True,
    )


# ============================================================
# LECTURES
# ============================================================

@app.get("/api/lectures")
def lectures():

    subject = (
        request.args.get(
            "subject"
        )
        or ""
    ).strip()

    chapter = (
        request.args.get(
            "chapter"
        )
        or ""
    ).strip()

    exam_type = (
        request.args.get(
            "type"
        )
        or ""
    ).strip()

    query = " ".join(
        item
        for item in (
            "SamStudy",
            exam_type,
            subject,
            chapter,
            "lecture",
        )
        if item
    )

    return jsonify(
        url=(
            "https://www.youtube.com/results?"
            "search_query="
            + quote_plus(query)
        ),
        query=query,
    )


# ============================================================
# BOOK VERIFICATION
# ============================================================

@app.post("/api/books/verify")
def verify_book():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    question = str(
        data.get(
            "question",
            "",
        )
    ).strip()

    filename = str(
        data.get(
            "book",
            "",
        )
    ).strip()

    if (
        not question
        or not filename
    ):

        return jsonify(
            error=(
                "Question and book "
                "filename are required."
            )
        ), 400

    safe_filename = Path(
        filename
    ).name

    path = (
        BOOKS
        / safe_filename
    )

    if not path.exists():

        return jsonify(
            error=(
                "Book not found. "
                "Upload it from "
                "Developer Panel first."
            )
        ), 404

    try:

        from pypdf import PdfReader

        reader = PdfReader(
            str(path)
        )

        terms = [
            term.lower()
            for term in re.findall(
                r"[A-Za-z]{4,}",
                question,
            )
        ]

        hits = []

        for index, page in enumerate(
            reader.pages
        ):

            text = (
                page.extract_text()
                or ""
            )

            lower = text.lower()

            score = sum(
                lower.count(term)
                for term in terms[:12]
            )

            if score:

                hits.append(
                    (
                        score,
                        index + 1,
                        text[:5000],
                    )
                )

        hits = sorted(
            hits,
            reverse=True,
        )[:5]

        evidence = "\n\n".join(
            (
                f"[Book page {page}]\n"
                f"{text}"
            )
            for _, page, text in hits
        )

        prompt = f"""
Answer using only these book excerpts.

Question:
{question}

Evidence:
{evidence or "No matching excerpt found."}

Clearly state if evidence is insufficient.

Include a Sources section
with page numbers.
"""

        text, _ = gemini(
            prompt,
            grounded=False,
        )

        return jsonify(
            answer=text,
            book=path.name,
            pages=[
                page
                for _, page, _ in hits
            ],
            source="Uploaded book + Gemini",
        )

    except Exception as exc:

        return jsonify(
            error=str(exc)
        ), 500


# ============================================================
# DOUBT PDF
# ============================================================

@app.post("/api/doubt/pdf")
def doubt_pdf():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    answer = str(
        data.get(
            "answer",
            "",
        )
    ).strip()

    question = str(
        data.get(
            "question",
            "",
        )
    ).strip()

    if not answer:

        return jsonify(
            error="No answer supplied."
        ), 400

    try:

        from reportlab.lib.pagesizes import A4

        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
        )

        from reportlab.lib.styles import (
            getSampleStyleSheet,
        )

        filename = (
            "doubt_"
            + secrets.token_hex(8)
            + ".pdf"
        )

        path = (
            GENERATED
            / filename
        )

        document = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        )

        styles = (
            getSampleStyleSheet()
        )

        story = [
            Paragraph(
                "SamStudy — AI Doubt Solution",
                styles["Title"],
            ),
            Spacer(1, 12),
        ]

        if question:

            story.extend(
                [
                    Paragraph(
                        "Question",
                        styles["Heading2"],
                    ),
                    Paragraph(
                        re.sub(
                            r"[<>]",
                            "",
                            question,
                        ),
                        styles["BodyText"],
                    ),
                    Spacer(1, 10),
                ]
            )

        clean = re.sub(
            r"[<>]",
            "",
            answer,
        )

        clean = (
            clean
            .replace(
                "&",
                "&amp;",
            )
            .replace(
                "\n",
                "<br/>",
            )
        )

        story.extend(
            [
                Paragraph(
                    "Solution",
                    styles["Heading2"],
                ),
                Paragraph(
                    clean,
                    styles["BodyText"],
                ),
                Spacer(1, 12),
                Paragraph(
                    (
                        "Generated with SamStudy AI. "
                        "Verify important facts "
                        "against cited material."
                    ),
                    styles["Italic"],
                ),
            ]
        )

        document.build(story)

        return jsonify(
            download=(
                "/generated/"
                + filename
            )
        )

    except Exception as exc:

        return jsonify(
            error=str(exc)
        ), 500


# ============================================================
# ADMIN
# ============================================================

@app.post("/api/admin/batch")
@require_admin
def admin_batch():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    name = str(
        data.get(
            "name",
            "",
        )
    ).strip()

    parent = str(
        data.get(
            "parent",
            "",
        )
    ).strip()

    exam_type = str(
        data.get(
            "type",
            "",
        )
    ).strip()

    if (
        not name
        or not parent
        or not exam_type
    ):

        return jsonify(
            error=(
                "Batch name, course/exam "
                "and type are required."
            )
        ), 400

    items = changes()

    items.append(
        {
            "kind": "batch",
            "name": name,
            "parent": parent,
            "type": exam_type,
            "createdAt": (
                datetime.utcnow()
                .isoformat()
            ),
        }
    )

    save_changes(items)

    return jsonify(ok=True)


@app.post("/api/admin/resource")
@require_admin
def admin_resource():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    url = str(
        data.get(
            "url",
            "",
        )
    ).strip()

    subject = str(
        data.get(
            "subject",
            "",
        )
    ).strip()

    parent = str(
        data.get(
            "parent",
            "",
        )
    ).strip()

    exam_type = str(
        data.get(
            "type",
            "",
        )
    ).strip()

    resource_kind = str(
        data.get(
            "resourceKind",
            "Notes",
        )
    ).strip()

    if (
        not url
        or not subject
    ):

        return jsonify(
            error=(
                "Resource URL and "
                "subject are required."
            )
        ), 400

    items = changes()

    items.append(
        {
            "kind": "resource",
            "resourceKind": resource_kind,
            "subject": subject,
            "parent": parent,
            "type": exam_type,
            "url": url,
            "createdAt": (
                datetime.utcnow()
                .isoformat()
            ),
        }
    )

    save_changes(items)

    return jsonify(ok=True)


@app.post("/api/admin/upload")
@require_admin
def admin_upload():

    uploaded = request.files.get(
        "file"
    )

    kind = request.form.get(
        "kind",
        "content",
    )

    if (
        not uploaded
        or not uploaded.filename
    ):

        return jsonify(
            error="Choose a file."
        ), 400

    safe_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        uploaded.filename,
    )

    target = (
        BOOKS
        if kind == "book"
        else CONTENT
    )

    uploaded.save(
        target / safe_name
    )

    prefix = (
        "/books/"
        if kind == "book"
        else "/content/"
    )

    return jsonify(
        ok=True,
        name=safe_name,
        url=prefix + safe_name,
    )


# ============================================================
# STUDY SHIELD
# ============================================================

@app.get("/api/shield")
@require_user
def shield_get():

    user = request_user()

    con = db()

    rows = con.execute(
        """
        SELECT *
        FROM shield_rules
        WHERE uid=?
        ORDER BY app_name
        """,
        (
            user["uid"],
        ),
    ).fetchall()

    con.close()

    return jsonify(
        rules=[
            dict(row)
            for row in rows
        ]
    )


@app.post("/api/shield")
@require_user
def shield_save():

    user = request_user()

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    name = str(
        data.get(
            "app_name",
            "",
        )
    ).strip()

    try:

        minutes = int(
            data.get(
                "minutes",
                60,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        minutes = 60

    minutes = max(
        1,
        min(
            minutes,
            1440,
        ),
    )

    reset_time = str(
        data.get(
            "reset_time",
            "00:00",
        )
    )

    if not name:

        return jsonify(
            error="App name required."
        ), 400

    con = db()

    cursor = con.execute(
        """
        INSERT INTO shield_rules(
            uid,
            app_name,
            minutes,
            reset_time,
            created_at
        )
        VALUES(?,?,?,?,?)
        """,
        (
            user["uid"],
            name,
            minutes,
            reset_time,
            datetime.utcnow().isoformat(),
        ),
    )

    con.commit()

    rule_id = cursor.lastrowid

    con.close()

    return jsonify(
        ok=True,
        id=rule_id,
    )


@app.delete("/api/shield/<int:rule_id>")
@require_user
def shield_delete(rule_id):

    user = request_user()

    con = db()

    con.execute(
        """
        DELETE FROM shield_rules
        WHERE id=? AND uid=?
        """,
        (
            rule_id,
            user["uid"],
        ),
    )

    con.commit()

    con.close()

    return jsonify(ok=True)


# ============================================================
# PROGRESS
# ============================================================

@app.post("/api/progress")
@require_user
def progress_save():

    user = request_user()

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    resource = str(
        data.get(
            "resource",
            "",
        )
    )

    try:

        value = float(
            data.get(
                "value",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        value = 0.0

    if not resource:

        return jsonify(
            error="Resource required."
        ), 400

    con = db()

    con.execute(
        """
        INSERT INTO progress(
            uid,
            resource,
            value,
            updated_at
        )
        VALUES(?,?,?,?)
        ON CONFLICT(uid,resource)
        DO UPDATE SET
            value=excluded.value,
            updated_at=excluded.updated_at
        """,
        (
            user["uid"],
            resource,
            value,
            datetime.utcnow().isoformat(),
        ),
    )

    con.commit()

    con.close()

    return jsonify(ok=True)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify(
        error="Uploaded file is too large."
    ), 413


@app.errorhandler(500)
def internal_error(error):

    return jsonify(
        error="Internal server error."
    ), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000",
            )
        ),
        debug=False,
    )




