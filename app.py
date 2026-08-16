import os
import json
import random
import re
import hashlib
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    abort,
)

from firebase_admin import (
    credentials,
    firestore,
    initialize_app,
    auth as fb_auth,
)

import firebase_admin


# =========================================================
# OPTIONAL GEMINI
# =========================================================

try:
    from google import genai
except Exception:
    genai = None


# =========================================================
# APP
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = (
    BASE_DIR /
    "static" /
    "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = (
    25 * 1024 * 1024
)


# =========================================================
# ENVIRONMENT
# =========================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "samshad0142@gmail.com"
).strip().lower()

FIREBASE_PROJECT_ID = os.getenv(
    "FIREBASE_PROJECT_ID",
    "sam-study-e9481"
)


# =========================================================
# FIREBASE ADMIN
# =========================================================

firebase_ready = False
db = None


def init_firebase():

    global firebase_ready
    global db

    if firebase_ready:
        return True

    try:

        service_json = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_JSON",
            ""
        ).strip()

        service_file = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            ""
        ).strip()


        if service_json:

            cred = credentials.Certificate(
                json.loads(service_json)
            )

        elif (
            service_file and
            Path(service_file).exists()
        ):

            cred = credentials.Certificate(
                service_file
            )

        else:

            cred = credentials.ApplicationDefault()


        if not firebase_admin._apps:

            initialize_app(
                cred,
                {
                    "projectId":
                    FIREBASE_PROJECT_ID
                }
            )


        db = firestore.client()

        firebase_ready = True

        return True

    except Exception as exc:

        app.logger.warning(
            "Firebase Admin not ready: %s",
            exc
        )

        return False


init_firebase()


# =========================================================
# FIREBASE WEB CONFIG
# =========================================================

@app.get("/api/firebase-config")
def firebase_config():

    return jsonify({

        "apiKey":
            os.getenv(
                "FIREBASE_API_KEY",
                ""
            ),

        "authDomain":
            os.getenv(
                "FIREBASE_AUTH_DOMAIN",
                f"{FIREBASE_PROJECT_ID}.firebaseapp.com"
            ),

        "projectId":
            FIREBASE_PROJECT_ID,

        "storageBucket":
            os.getenv(
                "FIREBASE_STORAGE_BUCKET",
                ""
            ),

        "messagingSenderId":
            os.getenv(
                "FIREBASE_MESSAGING_SENDER_ID",
                ""
            ),

        "appId":
            os.getenv(
                "FIREBASE_APP_ID",
                ""
            ),
    })


# =========================================================
# AUTH HELPERS
# =========================================================

def bearer_token():

    header = request.headers.get(
        "Authorization",
        ""
    )

    if not header.startswith(
        "Bearer "
    ):
        return None

    return header.split(
        " ",
        1
    )[1].strip()


def current_user(required=True):

    token = bearer_token()

    if not token:

        if required:
            abort(
                401,
                description=
                "Authentication required."
            )

        return None


    if not init_firebase():

        if required:
            abort(
                503,
                description=
                "Firebase Admin is not configured on the server."
            )

        return None


    try:

        return fb_auth.verify_id_token(
            token
        )

    except Exception:

        if required:
            abort(
                401,
                description=
                "Invalid or expired Firebase session."
            )

        return None


def admin_required(fn):

    @wraps(fn)
    def wrapped(
        *args,
        **kwargs
    ):

        user = current_user(
            True
        )

        email = (
            user.get("email") or ""
        ).lower()


        if email != ADMIN_EMAIL:

            abort(
                403,
                description=
                "Developer/admin access required."
            )


        return fn(
            *args,
            **kwargs
        )

    return wrapped


# =========================================================
# ERROR HANDLER
# =========================================================

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
def api_error(err):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({

            "ok": False,

            "error":
                getattr(
                    err,
                    "description",
                    str(err)
                )

        }), err.code

    return err


# =========================================================
# PAGES
# =========================================================

@app.get("/")
def home():

    return render_template(
        "index.html"
    )


@app.get("/login")
def login():

    return render_template(
        "login.html"
    )


@app.get("/profile")
def profile():

    return render_template(
        "profile.html"
    )


@app.get("/signup")
def signup():

    return render_template(
        "signup.html"
    )


@app.get("/batches")
def batches():

    return render_template(
        "batches.html",
        subjects=YEAR_SUBJECTS
    )


@app.get("/notes")
def notes():

    return render_template(
        "notes.html"
    )
