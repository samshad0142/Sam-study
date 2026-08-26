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

# Gemini 3.7 Flash
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
# DATABASE
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
    {"exams": {}, "courses": {}},
)

CHAPTERS = load_json(
    CHAPTERS_FILE,
    {},
)


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
# USER / AUTH
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
# GEMINI 3.7 FLASH
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

    body = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {},
    }

    # Gemini 3.7 Flash:
    # temperature/top_p/top_k intentionally NOT used.
    if thinking_level:

        body["generationConfig"][
            "thinkingConfig"
        ] = {
            "thinkingLevel": thinking_level
        }

    if json_mode:

        body["generationConfig"][
            "responseMimeType"
        ] = "application/json"

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

    # Small retry for transient 429/5xx.
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

                    text = (
                        data["candidates"][0]
                        ["content"]["parts"][0]
                        ["text"]
                    )

                    return text, data

                except Exception:

                    raise RuntimeError(
                        "Gemini returned no usable answer."
                    )

            last_error = (
                f"Gemini API error "
                f"{response.status_code}: "
                f"{response.text[:1000]}"
            )

            # Retry only temporary failures.
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

    raise RuntimeError(last_error or "Gemini request failed.")


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(text):

    text = text.strip()

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

    return json.loads(text.strip())


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
# FALLBACK QUESTIONS
# ============================================================

DEFAULT_QUESTIONS = [

    {
        "question":
            "If a number is increased by 20%, "
            "the result is 240. "
            "What was the original number?",
        "options": [
            "180",
            "200",
            "220",
            "210",
        ],
        "answer": 1,
        "explanation":
            "Let the original number be x. "
            "Then 1.2x = 240, so x = 200.",
        "subject":
            "Quantitative Aptitude",
    },

    {
        "question":
            "Which data structure follows "
            "the FIFO principle?",
        "options": [
            "Stack",
            "Queue",
            "Tree",
            "Graph",
        ],
        "answer": 1,
        "explanation":
            "FIFO means First In, First Out, "
            "which is the defining behavior of a queue.",
        "subject":
            "Data Structures",
    },

    {
        "question":
            "What is the derivative of x²?",
        "options": [
            "x",
            "2x",
            "x²",
            "2",
        ],
        "answer": 1,
        "explanation":
            "Using the power rule, "
            "d(x²)/dx = 2x.",
        "subject":
            "Mathematics",
    },

    {
        "question":
            "What is the most abundant gas "
            "in Earth's atmosphere?",
        "options": [
            "Oxygen",
            "Nitrogen",
            "Carbon dioxide",
            "Hydrogen",
        ],
        "answer": 1,
        "explanation":
            "Nitrogen makes up about 78% "
            "of Earth's dry atmosphere.",
        "subject":
            "General Awareness",
    },

    {
        "question":
            "Solve: x² − 5x + 6 = 0.",
        "options": [
            "x = 1, 6",
            "x = 2, 3",
            "x = −2, −3",
            "x = 0, 5",
        ],
        "answer": 1,
        "explanation":
            "Factor: "
            "(x − 2)(
