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

for p in (
    DATA,
    UPLOADS,
    BOOKS,
    CONTENT,
    GENERATED,
):
    p.mkdir(parents=True, exist_ok=True)


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATES),
    static_folder=str(STATIC),
    static_url_path="/static",
)

app.secret_key = os.getenv(
    "SECRET_KEY",
    secrets.token_hex(32),
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
)

INSTAGRAM_URL = os.getenv(
    "INSTAGRAM_URL",
    "https://www.instagram.com/Sam_shad132/",
)


# ============================================================
# DATABASE / FILES
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


# ============================================================
# DATABASE
# ============================================================

def db():
    con = sqlite3.connect(DB)
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

    return salt.hex() + "$" + digest.hex()


def password_ok(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$", 1)

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
                    password_hash(ADMIN_PASSWORD),
                    "SamStudy Developer",
                    datetime.utcnow().isoformat(),
                ),
            )

        con.commit()

    con.close()


init_db()


# ============================================================
# AUTH / USERS
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
        from firebase_admin import credentials, auth

        if not firebase_admin._apps:

            raw = os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_JSON_B64",
                "",
            ).strip()

            raw_json = os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_JSON",
                "",
            ).strip()

            if raw:

                info = json.loads(
                    base64.b64decode(raw).decode()
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

        u = auth.verify_id_token(token)

        return {
            "uid": u.get("uid"),
            "email": (
                u.get("email") or ""
            ).lower(),
            "name": u.get("name") or "",
            "emailVerified": bool(
                u.get("email_verified")
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

        u = firebase_user_from_token(
            authz[7:]
        )

        if u:
            return u

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

        u = request_user()

        if (
            not u
            or (u.get("email") or "").lower()
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
                    ).decode(),
                }
            }
        )

    generation_config = {}

    if thinking_level:
        generation_config["thinkingConfig"] = {
            "thinkingLevel": thinking_level
        }

    if json_mode:
        generation_config["responseMimeType"] = (
            "application/json"
        )

    body = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": generation_config,
    }

    if grounded:

        body["tools"] = [
            {
                "google_search": {}
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

                try:

                    parts_result = (
                        data["candidates"][0]
                        ["content"]["parts"]
                    )

                    text_parts = []

                    for part in parts_result:

                        if isinstance(part, dict):

                            text_value = part.get("text")

                            if text_value:
                                text_parts.append(
                                    text_value
                                )

                    text = "\n".join(
                        text_parts
                    ).strip()

                    if not text:
                        raise RuntimeError(
                            "Gemini returned no usable answer."
                        )

                    return text, data

                except Exception as e:

                    raise RuntimeError(
                        "Gemini returned no usable answer: "
                        + str(e)
                    )

            last_error = (
                f"Gemini API error "
                f"{response.status_code}: "
                f"{response.text[:1200]}"
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
                time.sleep(2 ** attempt)

        except Exception as e:

            last_error = str(e)

            if attempt < 2:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        last_error or "Gemini request failed."
    )


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(text):

    text = (text or "").strip()

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

    try:
        return json.loads(text)
    except json.JSONDecodeError:

        start = text.find("[")

        if start >= 0:

            end = text.rfind("]")

            if end > start:

                return json.loads(
                    text[start:end + 1]
                )

        start = text.find("{")

        if start >= 0:

            end = text.rfind("}")

            if end > start:

                return json.loads(
                    text[start:end + 1]
                )

        raise


# ============================================================
# QUESTION ALLOCATION
# ============================================================

def allocation(n, pattern=None):

    comp = (
        (pattern or {})
        .get("composition")
        or {}
    )

    if (
        comp
        and sum(
            int(comp.get(k, 0))
            for k in (
                "pyq",
                "typed",
                "hard",
            )
        ) == n
    ):

        return (
            int(comp.get("pyq", 0)),
            int(comp.get("typed", 0)),
            int(comp.get("hard", 0)),
        )

    a = round(n * 0.60)
    b = round(n * 0.30)
    c = n - a - b

    return a, b, max(0, c)


# ============================================================
# SAFE FALLBACK QUESTION BANK
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
            "which is the defining behavior of a queue."
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
            "Factor the equation as "
            "(x − 2)(x − 3) = 0. "
            "Therefore x = 2 or x = 3."
        ),
        "subject": "Mathematics",
    },

]


def fallback_questions(
    n,
    exam,
    etype,
    subjects=None,
):

    subjects = subjects or []

    output = []

    for i in range(n):

        source = dict(
            DEFAULT_QUESTIONS[
                i % len(DEFAULT_QUESTIONS)
            ]
        )

        if subjects:
            source["subject"] = (
                subjects[i % len(subjects)]
            )

        source["sourceType"] = (
            "Offline fallback"
        )

        source["source"] = (
            "SamStudy safe fallback bank"
        )

        output.append(source)

    return output


# ============================================================
# PAGE ROUTES
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
        gemini_model=GEMINI_MODEL,
        localLogin=True,
        firebase=bool(
            os.getenv("FIREBASE_API_KEY")
        ),
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

    if (
        page in targets
        or page in {
            "batches",
            "subjects",
            "quiz",
            "profile",
            "admin",
        }
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

    d = request.get_json(
        silent=True
    ) or {}

    email = str(
        d.get("email", "")
    ).strip().lower()

    password = str(
        d.get("password", "")
    )

    name = str(
        d.get("name", "")
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

        cur = con.execute(
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

        uid = cur.lastrowid

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

    d = request.get_json(
        silent=True
    ) or {}

    email = str(
        d.get("email", "")
    ).strip().lower()

    password = str(
        d.get("password", "")
    )

    con = db()

    row = con.execute(
        """
        SELECT id,email,password_hash,name
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
        ),
        "authDomain": os.getenv(
            "FIREBASE_AUTH_DOMAIN",
            "",
        ),
        "projectId": os.getenv(
            "FIREBASE_PROJECT_ID",
            "",
        ),
        "storageBucket": os.getenv(
            "FIREBASE_STORAGE_BUCKET",
            "",
        ),
        "messagingSenderId": os.getenv(
            "FIREBASE_MESSAGING_SENDER_ID",
            "",
        ),
        "appId": os.getenv(
            "FIREBASE_APP_ID",
            "",
        ),
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
# CATALOG / BATCHES / CHAPTERS
# ============================================================

@app.get("/api/catalog")
def catalog():
    return jsonify(CATALOG)


@app.get("/api/chapters")
def chapters():

    subject = (
        request.args.get("subject")
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


def save_changes(arr):

    CHANGES.write_text(
        json.dumps(
            arr,
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

    arr = changes()

    uploaded = []

    for p in CONTENT.rglob("*"):

        if p.is_file():

            relative = str(
                p.relative_to(CONTENT)
            ).replace("\\", "/")

            uploaded.append(
                {
                    "kind": "resource",
                    "resourceKind": "Notes",
                    "subject": "",
                    "name": p.name,
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
        arr + uploaded
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

    d = request.get_json(
        silent=True
    ) or {}

    mode = str(
        d.get("mode", "quiz")
    ).lower()

    try:
        n = int(
            d.get(
                "count",
                10,
            )
        )
    except Exception:
        n = 10

    n = max(
        1,
        min(n, 200),
    )

    exam = str(
        d.get(
            "exam",
            "SSC",
        )
    )

    etype = str(
        d.get(
            "type",
            "",
        )
    )

    subjects = d.get(
        "subjects"
    ) or []

    if not isinstance(
        subjects,
        list,
    ):
        subjects = [
            str(subjects)
        ]

    pattern = d.get(
        "pattern"
    ) or {}

    pyq, typed, hard = allocation(
        n,
        pattern
        if mode == "test"
        else None,
    )

    composition = (
        f"exactly {pyq} PYQ, "
        f"{typed} PYQ-type, "
        f"{hard} HARDEST"
    )

    mode_name = (
        "TEST"
        if mode == "test"
        else "QUIZ"
    )

    prompt = f"""
You are SamStudy's real AI exam engine.

Generate exactly {n} multiple-choice questions.

Mode: {mode_name}

Exam:
{exam}

Exam Type:
{etype}

Subjects:
{", ".join(subjects) if subjects else "Mixed"}

Required composition:
{composition}

IMPORTANT RULES:

1. Return EXACTLY {n} questions.
2. Every question must have exactly 4 options.
3. "answer" must be an integer from 0 to 3.
4. Include a useful explanation.
5. Include subject.
6. Include sourceType.
7. Include source.
8. Never invent a real PYQ citation.
9. Use PYQ only when the question can be reliably identified.
10. Otherwise use PYQ-type.
11. Mathematical expressions must use clean Unicode or LaTeX.
12. Do not use decorative symbols.
13. Do not add emojis.
14. Do not add unnecessary symbols.
15. Do not put markdown outside the JSON.
16. Return JSON array only.

Each object must have:

question
options
answer
explanation
subject
sourceType
source

Test configuration:
{json.dumps(pattern, ensure_ascii=False)}
"""

    try:

        text, raw = gemini(
            prompt,
            json_mode=True,
            grounded=True,
            thinking_level="medium",
        )

        data = parse_json(text)

        if not isinstance(
            data,
            list,
        ):
            raise ValueError(
                "Gemini did not return an array."
            )

        clean_questions = []

        for item in data:

            if not isinstance(
                item,
                dict,
            ):
                continue

            question = str(
                item.get(
                    "question",
                    "",
                )
            ).strip()

            options = item.get(
                "options",
                [],
            )

            try:
                answer = int(
                    item.get(
                        "answer",
                        0,
                    )
                )
            except Exception:
                answer = 0

            if (
                not question
                or not isinstance(
                    options,
                    list,
                )
                or len(options) != 4
            ):
                continue

            answer = max(
                0,
                min(
                    3,
                    answer,
                ),
            )

            clean_questions.append(
                {
                    "question": question,
                    "options": [
                        str(x)
                        for x in options
                    ],
                    "answer": answer,
                    "explanation": str(
                        item.get(
                            "explanation",
                            "",
                        )
                    ),
                    "subject": str(
                        item.get(
                            "subject",
                            subjects[
                                0
                            ]
                            if subjects
                            else "",
                        )
                    ),
                    "sourceType": str(
                        item.get(
                            "sourceType",
                            "PYQ-type",
                        )
                    ),
                    "source": str(
                        item.get(
                            "source",
                            "Gemini generated",
                        )
                    ),
                }
            )

            if len(
                clean_questions
            ) >= n:
                break

        if len(
            clean_questions
        ) < n:

            raise RuntimeError(
                "Gemini returned fewer "
                "valid questions than requested."
            )

        return jsonify(
            questions=clean_questions,
            source="Gemini",
            model=GEMINI_MODEL,
            mode=mode,
        )

    except Exception as e:

        return jsonify(
            questions=fallback_questions(
                n,
                exam,
                etype,
                subjects,
            ),
            source="Offline safe bank",
            warning=str(e),
            model=GEMINI_MODEL,
            mode=mode,
        )


# Compatibility route
@app.post("/api/quiz")
def quiz_alias():
    return ai_quiz()


# ============================================================
# AI DOUBT SOLVER
# ============================================================

@app.post("/api/ai/doubt")
def ai_doubt():

    question = ""
    image = None
    mime = "image/jpeg"

    if request.files:

        question = (
            request.form.get(
                "question"
            )
            or ""
        ).strip()

        uploaded = request.files.get(
            "image"
        )

        if uploaded:

            image = uploaded.read()

            mime = (
                uploaded.mimetype
                or mime
            )

        track = (
            request.form.get(
                "track"
            )
            or ""
        )

        exam = (
            request.form.get(
                "exam"
            )
            or ""
        )

        exam_type = (
            request.form.get(
                "type"
            )
            or ""
        )

    else:

        d = request.get_json(
            silent=True
        ) or {}

        question = str(
            d.get(
                "question",
                "",
            )
        ).strip()

        img = d.get(
            "image"
        ) or {}

        track = str(
            d.get(
                "track",
                "",
            )
        )

        exam = str(
            d.get(
                "exam",
                "",
            )
        )

        exam_type = str(
            d.get(
                "type",
                "",
            )
        )

        if img.get("data"):

            try:

                image = base64.b64decode(
                    img["data"]
                )

                mime = (
                    img.get(
                        "mimeType"
                    )
                    or mime
                )

            except Exception:
                image = None

    if not question and not image:

        return jsonify(
            error=(
                "Enter a doubt or "
                "attach a photo."
            )
        ), 400

    prompt = f"""
You are SamStudy AI Tutor.

Solve the student's question clearly and step by step.

Student track:
{track}

Government exam:
{exam}

Exam type:
{exam_type}

Rules:

1. Explain the concept first when useful.
2. Then solve step by step.
3. Use correct mathematical notation.
4. Use Unicode such as x², √, ≤, ≥, ∑ when appropriate.
5. LaTeX is allowed when useful.
6. Never replace mathematical symbols with random decorative symbols.
7. Do not use unnecessary emojis.
8. Do not use decorative symbols.
9. Keep the explanation understandable for an exam student.
10. If a fact requires verification, clearly say so.
11. If source verification is possible, identify the source.
12. Never fabricate a book/page citation.

Student question:

{question if question else "Solve the attached image."}
"""

    try:

        text, raw = gemini(
            prompt,
            image_bytes=image,
            image_mime=mime,
            grounded=True,
            thinking_level="medium",
        )

        return jsonify(
            answer=text,
            source="Gemini",
            model=GEMINI_MODEL,
        )

    except Exception as e:

        return jsonify(
            answer=(
                "Gemini could not answer this "
                "request right now."
            ),
            source="Gemini error",
            warning=str(e),
            model=GEMINI_MODEL,
        )


# ============================================================
# AI 3D VISUALIZATION
# ============================================================

@app.post("/api/ai/3d")
def ai_3d():

    d = request.get_json(
        silent=True
    ) or {}

    concept = str(
        d.get(
            "concept",
            "",
        )
    ).strip()

    if not concept:

        return jsonify(
            error="Enter a concept."
        ), 400

    prompt = f"""
You are SamStudy's educational 3D visualization engine.

Create an educational 3D scene explaining:

{concept}

Return JSON only.

Required structure:

{{
  "title": "...",
  "explanation": "...",
  "objects": [
    {{
      "type": "box|sphere|cylinder|torus|plane|arrow",
      "x": 0,
      "y": 0,
      "z": 0,
      "scale": 1,
      "color": "#168cff",
      "label": "..."
    }}
  ]
}}

Rules:

- Maximum 12 objects.
- The objects must actually help explain the concept.
- Use arrows for relationships or directions.
- Use labels for important parts.
- Avoid decorative objects.
- Keep coordinates reasonable.
- Keep scale reasonable.
- Return valid JSON only.
"""

    try:

        text, raw = gemini(
            prompt,
            json_mode=True,
            thinking_level="low",
        )

        scene = parse_json(text)

        if not isinstance(
            scene,
            dict,
        ):
            raise ValueError(
                "Invalid 3D scene."
            )

        objects = scene.get(
            "objects",
            [],
        )

        if not isinstance(
            objects,
            list,
        ):
            objects = []

        return jsonify(
            title=scene.get(
                "title",
                concept,
            ),
            explanation=scene.get(
                "explanation",
                "",
            ),
            scene={
                "objects": objects[:12]
            },
            source="Gemini",
            model=GEMINI_MODEL,
        )

    except Exception as e:

        return jsonify(
            title=concept,
            explanation=(
                "Gemini could not generate "
                "a concept-specific scene."
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
            warning=str(e),
        )


# ============================================================
# AI NOTES + PDF
# ============================================================

@app.post("/api/ai/notes")
def ai_notes():

    d = request.get_json(
        silent=True
    ) or {}

    subject = str(
        d.get(
            "subject",
            "",
        )
    ).strip()

    chapter = str(
        d.get(
            "chapter",
            "",
        )
    ).strip()

    exam = str(
        d.get(
            "exam",
            "",
        )
    )

    exam_type = str(
        d.get(
            "type",
            "",
        )
    )

    if not subject or not chapter:

        return jsonify(
            error=(
                "Subject and chapter "
                "are required."
            )
        ), 400

    prompt = f"""
Create structured SamStudy study notes.

Exam:
{exam}

Exam type:
{exam_type}

Subject:
{subject}

Chapter:
{chapter}

Include:

1. Chapter overview
2. Important definitions
3. Core concepts
4. Important formulas
5. Solved examples
6. Common mistakes
7. Exam-focused points
8. Quick revision section

Mathematical notation must be clean.

Use:
x²
√
≤
≥
∑

or proper LaTeX.

Do not use decorative symbols.

Do not fabricate textbook citations.

If source verification is needed, clearly distinguish:
- textbook/general knowledge
- verified source information
"""

    try:

        text, raw = gemini(
            prompt,
            grounded=True,
            thinking_level="medium",
        )

    except Exception as e:

        text = (
            f"{chapter}\n\n"
            "Key concepts\n"
            "- Review the core definitions "
            "and formulas for this chapter.\n"
            "- Add examples from the "
            "prescribed textbook.\n\n"
            f"AI status: {e}"
        )

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

        path = (
            GENERATED
            / f"notes_{secrets.token_hex(8)}.pdf"
        )

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        )

        styles = getSampleStyleSheet()

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

        for block in re.split(
            r"\n\s*\n",
            text,
        ):

            clean = re.sub(
                r"[<>]",
                "",
                block,
            )

            clean = (
                clean
                .replace("&", "&amp;")
                .replace("\n", "<br/>")
            )

            story.append(
                Paragraph(
                    clean,
                    styles["BodyText"],
                )
            )

            story.append(
                Spacer(1, 8)
            )

        doc.build(story)

        return jsonify(
            download=(
                f"/generated/{path.name}"
            ),
            text=text,
            source="Gemini",
            model=GEMINI_MODEL,
        )

    except Exception as e:

        return jsonify(
            error=(
                f"PDF generation failed: {e}"
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
        x
        for x in [
            "SamStudy",
            exam_type,
            subject,
            chapter,
            "lecture",
        ]
        if x
    )

    return jsonify(
        url=(
            "https://www.youtube.com/results"
            "?search_query="
            + quote_plus(query)
        ),
        query=query,
    )


# ============================================================
# BOOK VERIFICATION
# ============================================================

@app.post("/api/books/verify")
def verify_book():

    d = request.get_json(
        silent=True
    ) or {}

    question = str(
        d.get(
            "question",
            "",
        )
    ).strip()

    filename = str(
        d.get(
            "book",
            "",
        )
    ).strip()

    if not question or not filename:

        return jsonify(
            error=(
                "Question and book "
                "filename are required."
            )
        ), 400

    path = (
        BOOKS
        / Path(filename).name
    )

    if not path.exists():

        return jsonify(
            error=(
                "Book not found. Upload it "
                "from Developer Panel first."
            )
        ), 404

    try:

        from pypdf import PdfReader

        reader = PdfReader(
            str(path)
        )

        terms = [
            t.lower()
            for t in re.findall(
                r"[A-Za-z]{4,}",
                question,
            )
        ]

        hits = []

        for i, page in enumerate(
            reader.pages
        ):

            text = (
                page.extract_text()
                or ""
            )

            low = text.lower()

            score = sum(
                low.count(term)
                for term in terms[:12]
            )

            if score:

                hits.append(
                    (
                        score,
                        i + 1,
                        text[:5000],
                    )
                )

        hits = sorted(
            hits,
            reverse=True,
        )[:5]

        evidence = "\n\n".join(
            f"[Book page {page}]\n{text}"
            for _, page, text
            in hits
        )

        prompt = f"""
Answer the question using ONLY
the supplied book evidence.

Question:
{question}

Book evidence:

{evidence or "No matching excerpt found."}

Rules:

1. Clearly state if evidence is insufficient.
2. Do not invent page numbers.
3. Include a Sources section.
4. Mention the actual page numbers from the evidence.
5. Mathematical symbols must be correct.
"""

        text, raw = gemini(
            prompt,
            grounded=False,
            thinking_level="medium",
        )

        return jsonify(
            answer=text,
            book=path.name,
            pages=[
                page
                for _, page, _
                in hits
            ],
            source=(
                "Uploaded book + Gemini"
            ),
            model=GEMINI_MODEL,
        )

    except Exception as e:

        return jsonify(
            error=str(e)
        ), 500


# ============================================================
# DOUBT PDF
# ============================================================

@app.post("/api/doubt/pdf")
def doubt_pdf():

    d = request.get_json(
        silent=True
    ) or {}

    answer = str(
        d.get(
            "answer",
            "",
        )
    ).strip()

    question = str(
        d.get(
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

        path = (
            GENERATED
            / f"doubt_{secrets.token_hex(8)}.pdf"
        )

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=42,
            rightMargin=42,
            topMargin=42,
            bottomMargin=42,
        )

        styles = getSampleStyleSheet()

        story = [
            Paragraph(
                "SamStudy — AI Doubt Solution",
                styles["Title"],
            ),
            Spacer(1, 12),
        ]

        if question:

            clean_question = re.sub(
                r"[<>]",
                "",
                question,
            )

            clean_question = (
                clean_question
                .replace("&", "&amp;")
                .replace("\n", "<br/>")
            )

            story += [
                Paragraph(
                    "Question",
                    styles["Heading2"],
                ),
                Paragraph(
                    clean_question,
                    styles["BodyText"],
                ),
                Spacer(1, 10),
            ]

        clean_answer = re.sub(
            r"[<>]",
            "",
            answer,
        )

        clean_answer = (
            clean_answer
            .replace("&", "&amp;")
            .replace("\n", "<br/>")
        )

        story += [
            Paragraph(
                "Solution",
                styles["Heading2"],
            ),
            Paragraph(
                clean_answer,
                styles["BodyText"],
            ),
            Spacer(1, 12),
            Paragraph(
                "Generated with SamStudy AI. "
                "Verify important facts against "
                "cited material.",
                styles["Italic"],
            ),
        ]

        doc.build(story)

        return jsonify(
            download=(
                f"/generated/{path.name}"
            )
        )

    except Exception as e:

        return jsonify(
            error=(
                f"PDF generation failed: {e}"
            )
        ), 500


# ============================================================
# ADMIN — BATCH
# ============================================================

@app.post("/api/admin/batch")
@require_admin
def admin_batch():

    d = request.get_json(
        silent=True
    ) or {}

    name = str(
        d.get(
            "name",
            "",
        )
    ).strip()

    parent = str(
        d.get(
            "parent",
            "",
        )
    ).strip()

    exam_type = str(
        d.get(
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

    arr = changes()

    arr.append(
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

    save_changes(arr)

    return jsonify(
        ok=True
    )


# ============================================================
# ADMIN — RESOURCE
# ============================================================

@app.post("/api/admin/resource")
@require_admin
def admin_resource():

    d = request.get_json(
        silent=True
    ) or {}

    url = str(
        d.get(
            "url",
            "",
        )
    ).strip()

    subject = str(
        d.get(
            "subject",
            "",
        )
    ).strip()

    parent = str(
        d.get(
            "parent",
            "",
        )
    ).strip()

    exam_type = str(
        d.get(
            "type",
            "",
        )
    ).strip()

    kind = str(
        d.get(
            "resourceKind",
            "Notes",
        )
    ).strip()

    if not url or not subject:

        return jsonify(
            error=(
                "Resource URL and "
                "subject are required."
            )
        ), 400

    arr = changes()

    arr.append(
        {
            "kind": "resource",
            "resourceKind": kind,
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

    save_changes(arr)

    return jsonify(
        ok=True
    )


# ============================================================
# ADMIN — UPLOAD
# ============================================================

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

    safe = re.sub(
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
        target / safe
    )

    return jsonify(
        ok=True,
        name=safe,
        url=(
            "/books/"
            if kind == "book"
            else "/content/"
        ) + safe,
    )


# ============================================================
# STUDY SHIELD
# ============================================================

@app.get("/api/shield")
@require_user
def shield_get():

    u = request_user()

    con = db()

    rows = con.execute(
        """
        SELECT *
        FROM shield_rules
        WHERE uid=?
        ORDER BY app_name
        """,
        (u["uid"],),
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

    u = request_user()

    d = request.get_json(
        silent=True
    ) or {}

    name = str(
        d.get(
            "app_name",
            "",
        )
    ).strip()

    try:

        minutes = int(
            d.get(
                "minutes",
                60,
            )
        )

    except Exception:

        minutes = 60

    minutes = max(
        1,
        min(
            minutes,
            1440,
        ),
    )

    reset_time = str(
        d.get(
            "reset_time",
            "00:00",
        )
    )

    enabled = 1 if d.get(
        "enabled",
        True,
    ) else 0

    if not name:

        return jsonify(
            error="App name required."
        ), 400

    con = db()

    cur = con.execute(
        """
        INSERT INTO shield_rules(
            uid,
            app_name,
            minutes,
            reset_time,
            enabled,
            created_at
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            u["uid"],
            name,
            minutes,
            reset_time,
            enabled,
            datetime.utcnow().isoformat(),
        ),
    )

    con.commit()

    rule_id = cur.lastrowid

    con.close()

    return jsonify(
        ok=True,
        id=rule_id,
    )


@app.delete("/api/shield/<int:rule_id>")
@require_user
def shield_delete(rule_id):

    u = request_user()

    con = db()

    con.execute(
        """
        DELETE FROM shield_rules
        WHERE id=? AND uid=?
        """,
        (
            rule_id,
            u["uid"],
        ),
    )

    con.commit()

    con.close()

    return jsonify(
        ok=True
    )


# ============================================================
# PROGRESS
# ============================================================

@app.post("/api/progress")
@require_user
def progress_save():

    u = request_user()

    d = request.get_json(
        silent=True
    ) or {}

    resource = str(
        d.get(
            "resource",
            "",
        )
    )

    try:

        value = float(
            d.get(
                "value",
                0,
            )
        )

    except Exception:

        value = 0

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
            u["uid"],
            resource,
            value,
            datetime.utcnow().isoformat(),
        ),
    )

    con.commit()

    con.close()

    return jsonify(
        ok=True
    )


@app.get("/api/progress")
@require_user
def progress_get():

    u = request_user()

    con = db()

    rows = con.execute(
        """
        SELECT resource,value,updated_at
        FROM progress
        WHERE uid=?
        ORDER BY updated_at DESC
        """,
        (u["uid"],),
    ).fetchall()

    con.close()

    return jsonify(
        progress=[
            dict(row)
            for row in rows
        ]
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
                "5000",
            )
        ),
        debug=False,
    )
