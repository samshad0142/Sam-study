import os
import json
import re
import sqlite3
import base64
import secrets
import hmac
import hashlib
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
    session
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
    static_url_path="/static"
)

app.secret_key = os.getenv(
    "SECRET_KEY",
    secrets.token_hex(32)
)

app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ============================================================
# ENVIRONMENT
# ============================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "samshad0142@gmail.com"
).strip().lower()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    ""
).strip()

GEMINI_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()

# Gemini 3.7 Flash
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.7-flash"
).strip()

YOUTUBE_URL = os.getenv(
    "YOUTUBE_URL",
    "https://www.youtube.com/@Sam_malik77"
)

INSTAGRAM_URL = os.getenv(
    "INSTAGRAM_URL",
    "https://www.instagram.com/Sam_shad132/"
)


# ============================================================
# FILES
# ============================================================

DB = DATA / "samstudy.db"
CHANGES = DATA / "changes.json"
CATALOG_FILE = DATA / "catalog.json"
CHAPTERS_FILE = DATA / "chapters.json"

if not CHANGES.exists():
    CHANGES.write_text(
        "[]",
        encoding="utf-8"
    )


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
        "courses": {}
    }
)

CHAPTERS = load_json(
    CHAPTERS_FILE,
    {}
)


# ============================================================
# DATABASE
# ============================================================

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


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
            (ADMIN_EMAIL,)
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
                    datetime.utcnow().isoformat()
                )
            )

            con.commit()

    con.close()


def password_hash(password):

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        180000
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
            1
        )

        got = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            180000
        ).hex()

        return hmac.compare_digest(
            got,
            digest_hex
        )

    except Exception:
        return False


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
        (uid,)
    ).fetchone()

    con.close()

    if not row:
        return None

    return {
        "uid": str(row["id"]),
        "email": row["email"],
        "name": row["name"] or "",
        "emailVerified": True,
        "local": True
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
                ""
            ).strip()

            raw_json = os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_JSON",
                ""
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
            )
        }

    except Exception:
        return None


def request_user():

    authz = request.headers.get(
        "Authorization",
        ""
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
    thinking_level="medium"
):

    if not GEMINI_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    import requests

    model = GEMINI_MODEL

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    parts = [
        {
            "text": prompt
        }
    ]

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if image_bytes:

        parts.append(
            {
                "inlineData": {
                    "mimeType": image_mime,
                    "data": base64.b64encode(
                        image_bytes
                    ).decode()
                }
            }
        )

    # --------------------------------------------------------
    # GENERATION CONFIG
    # --------------------------------------------------------

    generation_config = {
        "thinkingConfig": {
            "thinkingLevel": thinking_level
        }
    }

    if json_mode:

        generation_config[
            "responseMimeType"
        ] = "application/json"

    body = {

        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],

        "generationConfig":
            generation_config
    }

    # --------------------------------------------------------
    # GOOGLE SEARCH GROUNDING
    # --------------------------------------------------------

    if grounded:

        body["tools"] = [
            {
                "google_search": {}
            }
        ]

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_KEY
    }

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=180
    )

    if not response.ok:

        raise RuntimeError(
            "Gemini API error "
            f"{response.status_code}: "
            f"{response.text[:1500]}"
        )

    data = response.json()

    try:

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:

            raise RuntimeError(
                "Gemini returned no candidates."
            )

        content = candidates[0].get(
            "content",
            {}
        )

        response_parts = content.get(
            "parts",
            []
        )

        text_parts = []

        for part in response_parts:

            if "text" in part:
                text_parts.append(
                    part["text"]
                )

        text = "".join(
            text_parts
        ).strip()

        if not text:

            raise RuntimeError(
                "Gemini returned an empty answer."
            )

        return text, data

    except Exception as e:

        raise RuntimeError(
            f"Gemini response parsing failed: {e}"
        )


def parse_json(text):

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return json.loads(
        text.strip()
    )


# ============================================================
# QUESTION COMPOSITION
# ============================================================

def allocation(n, pattern=None):

    comp = (
        pattern or {}
    ).get("composition") or {}

    if comp:

        total = sum(
            int(comp.get(k, 0))
            for k in (
                "pyq",
                "typed",
                "hard"
            )
        )

        if total == n:

            return (
                int(comp.get("pyq", 0)),
                int(comp.get("typed", 0)),
                int(comp.get("hard", 0))
            )

    a = round(n * 0.60)
    b = round(n * 0.30)
    c = n - a - b

    return a, b, max(0, c)


# ============================================================
# PAGES
# ============================================================

@app.get("/")
def home():

    return render_template(
        "index.html",
        initial_page="home"
    )


@app.get("/preview")
def preview():

    return render_template(
        "index.html",
        initial_page="home"
    )


@app.get("/health")
def health():

    return jsonify(
        ok=True,
        ai=bool(GEMINI_KEY),
        geminiModel=GEMINI_MODEL,
        localLogin=True,
        firebase=bool(
            os.getenv("FIREBASE_API_KEY")
        )
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
        "3d": "three",

        "notes": "resource",
        "resource": "resource",

        "studyshield": "shield",
        "shield": "shield",

        "ai": "ai"
    }

    if (
        page in targets
        or page in {
            "batches",
            "subjects",
            "quiz",
            "profile",
            "admin"
        }
    ):

        return render_template(
            "index.html",
            initial_page=targets.get(
                page,
                page
            )
        )

    abort(404)


@app.get("/manifest.webmanifest")
def manifest():

    return send_from_directory(
        ROOT,
        "manifest.webmanifest"
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
                datetime.utcnow().isoformat()
            )
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
            "local": True
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
        SELECT
            id,
            email,
            password_hash,
            name
        FROM users
        WHERE email=?
        """,
        (email,)
    ).fetchone()

    con.close()

    if (
        not row
        or not password_ok(
            password,
            row["password_hash"]
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
            "local": True
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

        localLogin=True
    )


# ============================================================
# CATALOG
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
        ) or ""
    ).strip()

    fallback = [

        "Introduction",
        "Core Concepts",
        "Important Definitions",
        "Key Formulas / Rules",
        "Solved Examples",
        "Common Mistakes",
        "Practice Questions",
        "Revision"
    ]

    return jsonify(
        subject=subject,
        chapters=CHAPTERS.get(
            subject,
            fallback
        )
    )


def changes():

    return load_json(
        CHANGES,
        []
    )


def save_changes(arr):

    CHANGES.write_text(
        json.dumps(
            arr,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


@app.get("/api/catalog-changes")
def catalog_changes():

    return jsonify(
        changes()
    )


# ============================================================
# RESOURCES
# ============================================================

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
                            "/"
                        )
                    )
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
        as_attachment=False
    )


@app.get("/books/<path:name>")
def books(name):

    return send_from_directory(
        BOOKS,
        name,
        as_attachment=False
    )


# ============================================================
# GEMINI QUIZ / TEST
# ============================================================

@app.post("/api/ai/quiz")
def ai_quiz():

    d = request.get_json(
        silent=True
    ) or {}

    mode = str(
        d.get("mode", "quiz")
    ).lower()

    if mode not in (
        "quiz",
        "test"
    ):

        mode = "quiz"

    try:

        n = int(
            d.get(
                "count",
                10
            )
        )

    except Exception:

        n = 10

    n = max(
        1,
        min(n, 100)
    )

    exam = str(
        d.get(
            "exam",
            "SSC"
        )
    ).strip()

    etype = str(
        d.get(
            "type",
            ""
        )
    ).strip()

    subjects = d.get(
        "subjects"
    ) or []

    pattern = d.get(
        "pattern"
    ) or {}

    pyq, typed, hard = allocation(
        n,
        pattern if mode == "test"
        else None
    )

    if mode == "test":

        composition = (
            f"Exactly {pyq} PYQ, "
            f"{typed} PYQ-type and "
            f"{hard} hardest questions."
        )

    else:

        composition = (
            "Generate a balanced "
            "exam-practice quiz."
        )

    prompt = f"""
You are the official SamStudy AI Exam Engine.

Generate exactly {n} multiple-choice questions.

Exam:
{exam}

Exam type:
{etype}

Subjects:
{", ".join(subjects) if subjects else "Mixed"}

Mode:
{mode}

Question requirements:

1. Every question must have exactly 4 options.
2. answer must be an integer from 0 to 3.
3. Include a clear explanation.
4. Include subject.
5. Include sourceType.
6. Include source.
7. Use PYQ only when the question is genuinely
   verifiable as a previous-year question.
8. Never invent a PYQ year, paper or citation.
9. If it is not verified, use PYQ-type.
10. Mathematical notation must be clean.
11. Use Unicode or LaTeX for mathematics.
12. Do not use decorative unwanted symbols.
13. Do not output markdown.
14. Return JSON only.
15. The JSON must be an array.

Mode-specific requirements:

{composition}

For TEST mode follow this pattern:

{json.dumps(pattern, ensure_ascii=False)}

Required JSON object format:

[
  {{
    "question": "Question text",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer": 0,
    "explanation": "Explanation",
    "subject": "Subject",
    "sourceType": "PYQ-type",
    "source": "Source description"
  }}
]
"""

    try:

        text, raw = gemini(
            prompt,
            json_mode=True,
            grounded=True,
            thinking_level="medium"
        )

        questions = parse_json(
            text
        )

        if not isinstance(
            questions,
            list
        ):

            raise ValueError(
                "Gemini did not return an array."
            )

        if len(questions) < n:

            raise ValueError(
                f"Gemini returned only "
                f"{len(questions)} questions "
                f"out of requested {n}."
            )

        clean = []

        for q in questions[:n]:

            if not isinstance(
                q,
                dict
            ):
                continue

            options = q.get(
                "options"
            )

            if not isinstance(
                options,
                list
            ) or len(options) != 4:

                continue

            answer = q.get(
                "answer"
            )

            try:
                answer = int(answer)
            except Exception:
                continue

            if answer not in (
                0,
                1,
                2,
                3
            ):
                continue

            clean.append(
                {
                    "question": str(
                        q.get(
                            "question",
                            ""
                        )
                    ),

                    "options": [
                        str(x)
                        for x in options
                    ],

                    "answer": answer,

                    "explanation": str(
                        q.get(
                            "explanation",
                            ""
                        )
                    ),

                    "subject": str(
                        q.get(
                            "subject",
                            ""
                        )
                    ),

                    "sourceType": str(
                        q.get(
                            "sourceType",
                            "PYQ-type"
                        )
                    ),

                    "source": str(
                        q.get(
                            "source",
                            "Gemini-generated"
                        )
                    )
                }
            )

        if len(clean) < n:

            raise ValueError(
                "Gemini returned invalid "
                "question objects."
            )

        return jsonify(
            questions=clean,
            source="Gemini",
            model=GEMINI_MODEL,
            mode=mode
        )

    except Exception as e:

        # IMPORTANT:
        # No demo/fake questions are returned.
        # The frontend will receive the real AI error.

        return jsonify(
            error=str(e),
            source="Gemini",
            model=GEMINI_MODEL,
            mode=mode
        ), 502


# Compatibility endpoint
@app.post("/api/quiz")
def quiz_alias():

    return ai_quiz()


# ============================================================
# AI DOUBT SOLVER
# ============================================================

@app.post("/api/ai/doubt")
def ai_doubt():

    q = ""
    image = None
    mime = "image/jpeg"
    track = ""

    if request.files:

        q = (
            request.form.get(
                "question"
            ) or ""
        ).strip()

        track = (
            request.form.get(
                "track"
            ) or ""
        ).strip()

        f = request.files.get(
            "image"
        )

        if f:

            image = f.read()

            mime = (
                f.mimetype
                or mime
            )

    else:

        d = request.get_json(
            silent=True
        ) or {}

        q = str(
            d.get(
                "question",
                ""
            )
        ).strip()

        track = str(
            d.get(
                "track",
                ""
            )
        ).strip()

        img = d.get(
            "image"
        ) or {}

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

    if not q and not image:

        return jsonify(
            error=(
                "Enter a doubt or "
                "attach a photo."
            )
        ), 400

    prompt = f"""
You are SamStudy AI Tutor.

Student track:
{track}

Solve the student's doubt step by step.

Rules:

1. Explain in simple educational language.
2. Show the reasoning clearly.
3. Mathematical symbols must be correct.
4. Prefer clean notation such as:
   x², √, ≤, ≥, ∑, π
   or valid LaTeX.
5. Do not add decorative symbols.
6. Do not add unnecessary emojis.
7. If a factual claim needs verification,
   clearly identify it.
8. If the student asks for a book/source,
   distinguish verified material from explanation.
9. Never invent a book citation.
10. Make the final answer useful for exam preparation.

Student question:

{q or "Solve the attached image."}
"""

    try:

        text, _ = gemini(
            prompt,
            image_bytes=image,
            image_mime=mime,
            grounded=True,
            thinking_level="high"
        )

        return jsonify(
            answer=text,
            source="Gemini",
            model=GEMINI_MODEL
        )

    except Exception as e:

        return jsonify(
            error=str(e),
            source="Gemini",
            model=GEMINI_MODEL
        ), 502


# ============================================================
# AI 3D CONCEPT
# ============================================================

@app.post("/api/ai/3d")
def ai_3d():

    d = request.get_json(
        silent=True
    ) or {}

    concept = str(
        d.get(
            "concept",
            ""
        )
    ).strip()

    if not concept:

        return jsonify(
            error="Enter a concept."
        ), 400

    prompt = f"""
You are SamStudy's AI 3D visualization engine.

Create an educational 3D scene for:

{concept}

The scene must explain the concept,
not merely decorate it.

Return JSON only.

Format:

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
- Use simple educational geometry.
- Labels must explain the concept.
- Coordinates should be usable by a Three.js renderer.
- Do not use decorative symbols.
- Return JSON only.
"""

    try:

        text, _ = gemini(
            prompt,
            json_mode=True,
            grounded=True,
            thinking_level="medium"
        )

        scene = parse_json(
            text
        )

        return jsonify(
            title=scene.get(
                "title",
                concept
            ),

            explanation=scene.get(
                "explanation",
                ""
            ),

            scene=scene,

            source="Gemini",

            model=GEMINI_MODEL
        )

    except Exception as e:

        return jsonify(
            error=str(e),
            source="Gemini",
            model=GEMINI_MODEL
        ), 502


# ============================================================
# AI NOTES
# ============================================================

@app.post("/api/ai/notes")
def ai_notes():

    d = request.get_json(
        silent=True
    ) or {}

    subject = str(
        d.get(
            "subject",
            ""
        )
    ).strip()

    chapter = str(
        d.get(
            "chapter",
            ""
        )
    ).strip()

    exam = str(
        d.get(
            "exam",
            ""
        )
    ).strip()

    etype = str(
        d.get(
            "type",
            ""
        )
    ).strip()

    if not subject or not chapter:

        return jsonify(
            error=(
                "Subject and chapter "
                "are required."
            )
        ), 400

    prompt = f"""
You are SamStudy AI Notes Generator.

Create structured study notes for:

Exam:
{exam}

Exam type:
{etype}

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
8. Quick revision

Rules:

- Clean mathematical notation.
- Unicode or LaTeX is allowed.
- No decorative symbols.
- No fake citations.
- Clearly separate verified source information
  from general explanation.
- Use headings and readable formatting.
"""

    try:

        text, _ = gemini(
            prompt,
            grounded=True,
            thinking_level="medium"
        )

    except Exception as e:

        return jsonify(
            error=str(e),
            source="Gemini"
        ), 502

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    try:

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer
        )
        from reportlab.lib.styles import (
            getSampleStyleSheet
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
            bottomMargin=42
        )

        styles = getSampleStyleSheet()

        story = [

            Paragraph(
                "SamStudy — Chapter Notes",
                styles["Title"]
            ),

            Spacer(1, 12),

            Paragraph(
                f"{subject} — {chapter}",
                styles["Heading2"]
            ),

            Spacer(1, 10)
        ]

        for block in re.split(
            r"\n\s*\n",
            text
        ):

            clean = (
                re.sub(
                    r"[<>]",
                    "",
                    block
                )
                .replace(
                    "&",
                    "&amp;"
                )
                .replace(
                    "\n",
                    "<br/>"
                )
            )

            story.append(
                Paragraph(
                    clean,
                    styles["BodyText"]
                )
            )

            story.append(
                Spacer(1, 8)
            )

        doc.build(
            story
        )

        return jsonify(
            download=(
                f"/generated/{path.name}"
            ),
            text=text,
            source="Gemini",
            model=GEMINI_MODEL
        )

    except Exception as e:

        return jsonify(
            text=text,
            source="Gemini",
            error=(
                "PDF generation failed: "
                f"{e}"
            )
        ), 500


@app.get("/generated/<path:name>")
def generated(name):

    return send_from_directory(
        GENERATED,
        name,
        as_attachment=True
    )


# ============================================================
# LECTURES
# ============================================================

@app.get("/api/lectures")
def lectures():

    subject = (
        request.args.get(
            "subject"
        ) or ""
    ).strip()

    chapter = (
        request.args.get(
            "chapter"
        ) or ""
    ).strip()

    etype = (
        request.args.get(
            "type"
        ) or ""
    ).strip()

    query = " ".join(
        x
        for x in [
            "SamStudy",
            etype,
            subject,
            chapter,
            "lecture"
        ]
        if x
    )

    return jsonify(
        url=(
            "https://www.youtube.com/results?"
            "search_query="
            + quote_plus(query)
        ),

        query=query
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
            ""
        )
    ).strip()

    filename = str(
        d.get(
            "book",
            ""
        )
    ).strip()

    if not question or not filename:

        return jsonify(
            error=(
                "Question and book "
                "filename are required."
            )
        ), 400

    path = BOOKS / Path(
        filename
    ).name

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
            t.lower()
            for t in re.findall(
                r"[A-Za-z]{4,}",
                question
            )
        ]

        hits = []

        for i, p in enumerate(
            reader.pages
        ):

            txt = (
                p.extract_text()
                or ""
            )

            low = txt.lower()

            score = sum(
                low.count(t)
                for t in terms[:12]
            )

            if score:

                hits.append(
                    (
                        score,
                        i + 1,
                        txt[:5000]
                    )
                )

        hits = sorted(
            hits,
            reverse=True
        )[:5]

        evidence = "\n\n".join(
            f"[Book page {p}]\n{t}"
            for _, p, t in hits
        )

        prompt = f"""
You are SamStudy Book Verification AI.

Answer the question using ONLY
the supplied book evidence.

Question:
{question}

Book evidence:
{evidence or "No matching excerpt found."}

Rules:

1. Do not invent information.
2. Clearly state when evidence is insufficient.
3. Mention the relevant page numbers.
4. Add a Sources section.
5. Separate book evidence from explanation.
"""

        text, _ = gemini(
            prompt,
            grounded=False,
            thinking_level="medium"
        )

        return jsonify(
            answer=text,
            book=path.name,
            pages=[
                p
                for _, p, _
                in hits
            ],
            source=(
                "Uploaded book + Gemini"
            )
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
            ""
        )
    ).strip()

    question = str(
        d.get(
            "question",
            ""
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
            Spacer
        )

        from reportlab.lib.styles import (
            getSampleStyleSheet
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
            bottomMargin=42
        )

        styles = getSampleStyleSheet()

        story = [

            Paragraph(
                "SamStudy — AI Doubt Solution",
                styles["Title"]
            ),

            Spacer(1, 12)
        ]

        if question:

            story += [

                Paragraph(
                    "Question",
                    styles["Heading2"]
                ),

                Paragraph(
                    re.sub(
                        r"[<>]",
                        "",
                        question
                    ),
                    styles["BodyText"]
                ),

                Spacer(1, 10)
            ]

        clean = (
            re.sub(
                r"[<>]",
                "",
                answer
            )
            .replace(
                "&",
                "&amp;"
            )
            .replace(
                "\n",
                "<br/>"
            )
        )

        story += [

            Paragraph(
                "Solution",
                styles["Heading2"]
            ),

            Paragraph(
                clean,
                styles["BodyText"]
            ),

            Spacer(1, 12),

            Paragraph(
                "Generated with SamStudy AI. "
                "Verify important facts against "
                "cited material.",
                styles["Italic"]
            )
        ]

        doc.build(
            story
        )

        return jsonify(
            download=(
                f"/generated/{path.name}"
            )
        )

    except Exception as e:

        return jsonify(
            error=str(e)
        ), 500


# ============================================================
# ADMIN - BATCH
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
            ""
        )
    ).strip()

    parent = str(
        d.get(
            "parent",
            ""
        )
    ).strip()

    etype = str(
        d.get(
            "type",
            ""
        )
    ).strip()

    if not name or not parent or not etype:

        return jsonify(
            error=(
                "Batch name, "
                "course/exam and "
                "type are required."
            )
        ), 400

    arr = changes()

    arr.append(
        {
            "kind": "batch",
            "name": name,
            "parent": parent,
            "type": etype,
            "createdAt":
                datetime.utcnow().isoformat()
        }
    )

    save_changes(
        arr
    )

    return jsonify(
        ok=True
    )


# ============================================================
# ADMIN - RESOURCE
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
            ""
        )
    ).strip()

    subject = str(
        d.get(
            "subject",
            ""
        )
    ).strip()

    parent = str(
        d.get(
            "parent",
            ""
        )
    ).strip()

    etype = str(
        d.get(
            "type",
            ""
        )
    ).strip()

    kind = str(
        d.get(
            "resourceKind",
            "Notes"
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
            "type": etype,
            "url": url,
            "createdAt":
                datetime.utcnow().isoformat()
        }
    )

    save_changes(
        arr
    )

    return jsonify(
        ok=True
    )


# ============================================================
# ADMIN - UPLOAD
# ============================================================

@app.post("/api/admin/upload")
@require_admin
def admin_upload():

    f = request.files.get(
        "file"
    )

    kind = request.form.get(
        "kind",
        "content"
    )

    if not f or not f.filename:

        return jsonify(
            error="Choose a file."
        ), 400

    safe = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        f.filename
    )

    target = (
        BOOKS
        if kind == "book"
        else CONTENT
    )

    f.save(
        target / safe
    )

    return jsonify(
        ok=True,
        name=safe,
        url=(
            "/books/"
            if kind == "book"
            else "/content/"
        ) + safe
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
        (u["uid"],)
    ).fetchall()

    con.close()

    return jsonify(
        rules=[
            dict(r)
            for r in rows
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
            ""
        )
    ).strip()

    try:

        mins = int(
            d.get(
                "minutes",
                60
            )
        )

    except Exception:

        mins = 60

    mins = max(
        1,
        min(mins, 1440)
    )

    reset = str(
        d.get(
            "reset_time",
            "00:00"
        )
    )

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
            created_at
        )
        VALUES(?,?,?,?,?)
        """,
        (
            u["uid"],
            name,
            mins,
            reset,
            datetime.utcnow().isoformat()
        )
    )

    con.commit()

    rid = cur.lastrowid

    con.close()

    return jsonify(
        ok=True,
        id=rid
    )


@app.delete("/api/shield/<int:rule_id>")
@require_user
def shield_delete(rule_id):

    u = request_user()

    con = db()

    con.execute(
        """
        DELETE FROM shield_rules
        WHERE id=?
        AND uid=?
        """,
        (
            rule_id,
            u["uid"]
        )
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
            ""
        )
    )

    try:

        value = float(
            d.get(
                "value",
                0
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
            datetime.utcnow().isoformat()
        )
    )

    con.commit()

    con.close()

    return jsonify(
        ok=True
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):

    return jsonify(
        error="Route not found",
        path=request.path
    ), 404


@app.errorhandler(413)
def too_large(e):

    return jsonify(
        error="Uploaded file is too large."
    ), 413


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
        ),
        debug=False
    )
