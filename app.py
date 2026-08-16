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
    abort
)

from firebase_admin import (
    credentials,
    firestore,
    initialize_app,
    auth as fb_auth
)

import firebase_admin


# =========================================================
# GEMINI
# =========================================================

try:
    from google import genai
except Exception:
    genai = None


# =========================================================
# APP
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


# =========================================================
# CONFIG
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
            service_file
            and Path(service_file).exists()
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
            os.getenv(
                "FIREBASE_PROJECT_ID",
                FIREBASE_PROJECT_ID
            ),

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
            )

    })


# =========================================================
# AUTH HELPERS
# =========================================================

def bearer_token():

    header = request.headers.get(
        "Authorization",
        ""
    )

    if not header.startswith("Bearer "):
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

        user = current_user(True)

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
# ERROR HANDLING
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


@app.get("/signup")
def signup():
    return render_template(
        "signup.html"
    )


@app.get("/profile")
def profile():
    return render_template(
        "profile.html"
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


@app.get("/quiz")
def quiz():
    return render_template(
        "quiz.html"
    )


@app.get("/doubt")
def doubt():
    return render_template(
        "doubt.html"
    )


@app.get("/3d")
def three_d():
    return render_template(
        "three_d.html"
    )


@app.get("/admin")
def admin():
    return render_template(
        "admin.html"
    )


# =========================================================
# SUBJECT DATA
# =========================================================

YEAR_SUBJECTS = {

    "1": [
        "Engineering Mathematics-I",
        "Engineering Physics",
        "Engineering Chemistry",
        "Programming for Problem Solving",
        "Fundamentals of Electrical Engineering",
        "Fundamentals of Electronics Engineering",
        "Environment & Ecology"
    ],

    "2": [
        "Engineering Mathematics-III",
        "Data Structures",
        "Discrete Mathematics",
        "Object Oriented Programming",
        "Digital Logic Design",
        "Computer Organization",
        "Operating Systems"
    ],

    "3": [
        "Design & Analysis of Algorithms",
        "Database Management Systems",
        "Computer Networks",
        "Theory of Computation",
        "Software Engineering",
        "Web Technology",
        "Artificial Intelligence"
    ],

    "4": [
        "Machine Learning",
        "Compiler Design",
        "Cloud Computing",
        "Cyber Security",
        "Distributed Systems",
        "Internet of Things",
        "Project / Major Project"
    ]

}


COURSE_SUBJECTS = {

    "BCA": [
        "Programming in C",
        "Data Structures",
        "Database Management Systems",
        "Computer Networks",
        "Operating Systems",
        "Web Technology",
        "Computer Organization"
    ],

    "MCA": [
        "Data Structures",
        "Algorithms",
        "Database Management Systems",
        "Operating Systems",
        "Computer Networks",
        "Software Engineering",
        "Artificial Intelligence"
    ],

    "M.Tech": [
        "Advanced Data Structures",
        "Advanced Algorithms",
        "Machine Learning",
        "Artificial Intelligence",
        "Research Methodology",
        "Advanced Computer Networks"
    ],

    "B.Pharm": [
        "Human Anatomy",
        "Pharmaceutics",
        "Pharmaceutical Chemistry",
        "Pharmacology",
        "Biochemistry",
        "Microbiology"
    ],

    "B.Sc": [
        "Physics",
        "Chemistry",
        "Mathematics",
        "Computer Science",
        "Biology",
        "Statistics"
    ]

}


EXAM_SUBJECTS = {

    "JEE Mains": [
        "Physics",
        "Chemistry",
        "Mathematics"
    ],

    "JEE Advanced": [
        "Physics",
        "Chemistry",
        "Mathematics"
    ],

    "GATE": [
        "General Aptitude",
        "Engineering Mathematics",
        "Programming",
        "Data Structures",
        "Algorithms",
        "Computer Networks",
        "Operating Systems",
        "DBMS"
    ],

    "SSC": [
        "Quantitative Aptitude",
        "Reasoning",
        "English",
        "General Awareness"
    ],

    "Railway": [
        "Mathematics",
        "Reasoning",
        "General Science",
        "General Awareness"
    ],

    "UPSC": [
        "History",
        "Geography",
        "Polity",
        "Economy",
        "Science & Technology",
        "Current Affairs"
    ],

    "Army": [
        "Mathematics",
        "Reasoning",
        "General Knowledge",
        "English",
        "General Science"
    ],

    "NEET UG": [
        "Physics",
        "Chemistry",
        "Biology"
    ],

    "NEET PG": [
        "Medicine",
        "Surgery",
        "Pharmacology",
        "Pathology"
    ]

}


# =========================================================
# PUBLIC NOTES
# =========================================================

@app.get("/api/batches")
def api_batches():

    if not init_firebase():

        return jsonify({
            "ok": True,
            "batches": []
        })


    docs = (
        db.collection("batches")
        .order_by("year")
        .stream()
    )


    data = []


    for d in docs:

        item = d.to_dict()

        item["id"] = d.id

        data.append(item)


    return jsonify({

        "ok": True,

        "batches": data

    })


@app.get("/api/notes")
def api_notes():

    year = request.args.get(
        "year",
        ""
    ).strip()

    subject = request.args.get(
        "subject",
        ""
    ).strip()

    unit = request.args.get(
        "unit",
        ""
    ).strip()


    if not init_firebase():

        return jsonify({

            "ok": True,

            "notes": []

        })


    ref = db.collection(
        "notes"
    )


    if year:

        ref = ref.where(
            "year",
            "==",
            year
        )


    if subject:

        ref = ref.where(
            "subject",
            "==",
            subject
        )


    if unit:

        ref = ref.where(
            "unit",
            "==",
            unit
        )


    data = []


    for d in ref.stream():

        item = d.to_dict()

        item["id"] = d.id

        data.append(item)


    data.sort(
        key=lambda x: (
            str(x.get("year", "")),
            str(x.get("subject", "")),
            str(x.get("unit", ""))
        )
    )


    return jsonify({

        "ok": True,

        "notes": data

    })


# =========================================================
# DOWNLOAD
# =========================================================

@app.get("/download/<path:filename>")
def download(filename):

    safe_name = Path(
        filename
    ).name

    path = UPLOAD_DIR / safe_name


    if not path.exists():

        abort(
            404,
            description=
            "File not found."
        )


    return send_from_directory(
        UPLOAD_DIR,
        safe_name,
        as_attachment=True
    )


# =========================================================
# ADMIN
# =========================================================

@app.get("/api/admin/status")
@admin_required
def admin_status():

    return jsonify({

        "ok": True,

        "admin": True,

        "email": ADMIN_EMAIL

    })


@app.post("/api/admin/batches")
@admin_required
def create_batch():

    payload = (
        request.get_json(
            silent=True
        ) or {}
    )


    year = str(
        payload.get(
            "year",
            ""
        )
    ).strip()


    name = str(
        payload.get(
            "name",
            ""
        )
    ).strip()


    description = str(
        payload.get(
            "description",
            ""
        )
    ).strip()


    if (
        year not in
        {"1", "2", "3", "4"}
        or not name
    ):

        abort(
            400,
            description=
            "Year and batch name are required."
        )


    ref = db.collection(
        "batches"
    ).add({

        "year": year,

        "name": name,

        "description":
            description,

        "createdBy":
            ADMIN_EMAIL,

        "createdAt":
            firestore.SERVER_TIMESTAMP

    })


    return jsonify({

        "ok": True,

        "id": ref[1].id

    })


@app.post("/api/admin/notes")
@admin_required
def create_note():

    title = request.form.get(
        "title",
        ""
    ).strip()

    year = request.form.get(
        "year",
        ""
    ).strip()

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    unit = request.form.get(
        "unit",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    file = request.files.get(
        "file"
    )


    if (
        not title
        or year not in
        {"1", "2", "3", "4"}
        or not subject
        or not unit
    ):

        abort(
            400,
            description=
            "Title, year, subject and unit are required."
        )


    if not file or not file.filename:

        abort(
            400,
            description=
            "Select a PDF/file to upload."
        )


    original = Path(
        file.filename
    ).name


    ext = Path(
        original
    ).suffix.lower()


    allowed = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".txt"
    }


    if ext not in allowed:

        abort(
            400,
            description=
            "Allowed files: PDF, DOC, DOCX, PPT, PPTX, TXT."
        )


    safe = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "_",
        original
    )


    safe = (
        f"{random.randint(100000,999999)}_"
        f"{safe}"
    )


    file.save(
        UPLOAD_DIR / safe
    )


    ref = db.collection(
        "notes"
    ).add({

        "title": title,

        "year": year,

        "subject": subject,

        "unit": unit,

        "description":
            description,

        "filename":
            safe,

        "originalName":
            original,

        "createdBy":
            ADMIN_EMAIL,

        "createdAt":
            firestore.SERVER_TIMESTAMP

    })


    return jsonify({

        "ok": True,

        "id": ref[1].id

    })


# =========================================================
# GEMINI
# =========================================================

def ai_client():

    if genai is None:
        return None


    key = os.getenv(
        "GEMINI_API_KEY",
        ""
    ).strip()


    if not key:
        return None


    try:

        return genai.Client(
            api_key=key
        )

    except Exception:

        return None


def generate_ai(prompt):

    client = ai_client()

    if client is None:
        return None


    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )


    response = client.models.generate_content(

        model=model,

        contents=prompt

    )


    return (
        response.text or ""
    ).strip()


# =========================================================
# QUIZ HELPERS
# =========================================================

def clean_json_text(text):

    if not text:
        return None


    text = text.strip()


    # Remove markdown code fences

    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.I
    )


    text = re.sub(
        r"```$",
        "",
        text
    )


    text = text.strip()


    match = re.search(
        r"\[[\s\S]*\]",
        text
    )


    if not match:
        return None


    try:

        data = json.loads(
            match.group(0)
        )

        return data

    except Exception:

        return None


def validate_questions(
    data,
    requested_count
):

    if not isinstance(
        data,
        list
    ):
        return []


    result = []


    seen = set()


    for item in data:

        if not isinstance(
            item,
            dict
        ):
            continue


        question = str(
            item.get(
                "question",
                ""
            )
        ).strip()


        options = item.get(
            "options",
            []
        )


        explanation = str(
            item.get(
                "explanation",
                ""
            )
        ).strip()


        try:

            answer = int(
                item.get(
                    "answer",
                    -1
                )
            )

        except Exception:

            continue


        if not question:
            continue


        if (
            not isinstance(
                options,
                list
            )
            or len(options) != 4
        ):
            continue


        options = [
            str(x).strip()
            for x in options
        ]


        if any(
            not x for x in options
        ):
            continue


        if answer not in {
            0, 1, 2, 3
        }:
            continue


        key = hashlib.sha256(
            question.lower()
            .encode("utf-8")
        ).hexdigest()


        if key in seen:
            continue


        seen.add(key)


        result.append({

            "question":
                question,

            "options":
                options,

            "answer":
                answer,

            "explanation":
                explanation

        })


        if len(result) >= requested_count:
            break


    return result


def fallback_quiz(
    course,
    year,
    level,
    exam,
    subject,
    count
):

    bank = {

        "Programming for Problem Solving": [

            (
                "Which data type is commonly used "
                "for an integer in C?",

                [
                    "int",
                    "float",
                    "char",
                    "double"
                ],

                0,

                "The int data type is commonly "
                "used for integer values in C."
            ),

            (
                "Which symbol terminates a C statement?",

                [
                    ";",
                    ":",
                    ".",
                    ","
                ],

                0,

                "A semicolon terminates most "
                "C statements."
            )

        ],


        "Data Structures": [

            (
                "Which data structure follows LIFO?",

                [
                    "Queue",
                    "Stack",
                    "Tree",
                    "Graph"
                ],

                1,

                "A stack follows Last In First Out."
            ),

            (
                "Which data structure follows FIFO?",

                [
                    "Stack",
                    "Queue",
                    "Heap",
                    "Tree"
                ],

                1,

                "A queue follows First In First Out."
            )

        ],


        "Operating Systems": [

            (
                "Which is a CPU scheduling algorithm?",

                [
                    "FCFS",
                    "DFS",
                    "BFS",
                    "Dijkstra"
                ],

                0,

                "FCFS means First Come First Served "
                "and is a CPU scheduling algorithm."
            )

        ],


        "Database Management Systems": [

            (
                "Which language is commonly used "
                "to query relational databases?",

                [
                    "HTML",
                    "SQL",
                    "CSS",
                    "C"
                ],

                1,

                "SQL is used to query and manage "
                "relational databases."
            )

        ],


        "Engineering Mathematics-I": [

            (
                "The derivative of x² is:",

                [
                    "x",
                    "2x",
                    "x²",
                    "2"
                ],

                1,

                "Using the power rule, "
                "d(x²)/dx = 2x."
            )

        ]

    }


    items = bank.get(
        subject
    )


    if not items:

        items = [

            (
                f"Which statement is most relevant "
                f"to {subject}?",

                [
                    f"A fundamental concept of {subject}",
                    "A random unrelated fact",
                    "A browser setting",
                    "A mobile notification"
                ],

                0,

                f"The first option represents "
                f"a fundamental concept of {subject}."
            )

        ]


    random.shuffle(
        items
    )


    result = []


    for q, options, answer, explanation in items:

        result.append({

            "question": q,

            "options": options,

            "answer": answer,

            "explanation": explanation

        })


        if len(result) >= count:
            break


    return result


# =========================================================
# AI QUIZ
# =========================================================

@app.post("/api/ai/quiz")
def ai_quiz():

    payload = (
        request.get_json(
            silent=True
        ) or {}
    )


    course = str(
        payload.get(
            "course",
            "B.Tech"
        )
    ).strip()


    year = str(
        payload.get(
            "year",
            "1"
        )
    ).strip()


    level = str(
        payload.get(
            "level",
            "Beginner"
        )
    ).strip()


    exam = str(
        payload.get(
            "exam",
            "AKTU"
        )
    ).strip()


    subject = str(
        payload.get(
            "subject",
            "General Studies"
        )
    ).strip()


    try:

        count = int(
            payload.get(
                "count",
                5
            )
        )

    except Exception:

        count = 5


    count = min(
        max(count, 3),
        50
    )


    # Random generation seed makes
    # repeated requests less likely to
    # produce identical sets.

    seed = random.randint(
        100000,
        999999999
    )


    prompt = f"""
You are the official-style question generation engine
for the SamStudy educational platform.

Create exactly {count} high-quality multiple-choice
questions.

STUDENT PROFILE:
Course/Class: {course}
Year/Class: {year}
Exam: {exam}
Subject: {subject}
Difficulty: {level}
Generation Seed: {seed}

IMPORTANT REQUIREMENTS:

1. Every question must be directly relevant to the
   selected course, exam and subject.

2. Follow the real syllabus, concepts, terminology,
   difficulty and question style associated with the
   selected exam.

3. Prefer conceptual, numerical, application-based and
   exam-relevant questions instead of generic trivia.

4. Questions should resemble the style and difficulty
   of previous-year questions (PYQ-style).

5. DO NOT claim that a generated question is an actual
   previous-year question unless the exact verified
   question is supplied as source material.

6. Do not invent a fake year, paper number or official
   PYQ attribution.

7. Do not repeat the same question within this response.

8. Make the question set varied.

9. Every question must have exactly four options.

10. Only one option may be correct.

11. The answer field must be the zero-based index:
    0, 1, 2 or 3.

12. Provide a detailed but student-friendly explanation
    after every answer.

13. For numerical questions, show the correct method,
    important formula and calculation in the explanation.

14. For theory questions, explain why the correct option
    is correct and briefly clarify the important concept.

15. Avoid ambiguous questions.

16. Do not include markdown outside the JSON.

RETURN ONLY VALID JSON.

FORMAT:

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
    "explanation": "Detailed explanation."
  }}
]
"""


    try:

        text = generate_ai(
            prompt
        )


        data = clean_json_text(
            text
        )


        questions = validate_questions(
            data,
            count
        )


        if len(questions) >= count:

            return jsonify({

                "ok": True,

                "source": "ai",

                "course":
                    course,

                "exam":
                    exam,

                "subject":
                    subject,

                "questions":
                    questions[:count]

            })


        if questions:

            app.logger.warning(
                "Gemini returned only %s/%s valid questions.",
                len(questions),
                count
            )


    except Exception as exc:

        app.logger.warning(
            "AI quiz error: %s",
            exc
        )


    # Fallback

    fallback = fallback_quiz(
        course,
        year,
        level,
        exam,
        subject,
        count
    )


    return jsonify({

        "ok": True,

        "source": "fallback",

        "course":
            course,

        "exam":
            exam,

        "subject":
            subject,

        "questions":
            fallback

    })


# =========================================================
# AI DOUBT
# =========================================================

@app.post("/api/ai/doubt")
def ai_doubt():

    payload = (
        request.get_json(
            silent=True
        ) or {}
    )


    doubt = str(
        payload.get(
            "doubt",
            ""
        )
    ).strip()


    context = str(
        payload.get(
            "context",
            ""
        )
    ).strip()


    if not doubt:

        abort(
            400,
            description=
            "Please enter your doubt."
        )


    prompt = f"""
You are SamStudy AI Doubt Solver.

Answer the student's doubt accurately,
clearly and step-by-step.

Context:
{context or "B.Tech / competitive exam study"}

Student doubt:
{doubt}

Rules:

- Start with the direct answer.
- Explain step-by-step.
- Use formulas and examples when useful.
- For numerical questions show calculations.
- For programming questions provide correct logic.
- If the question is ambiguous, state the assumption.
- Do not invent facts.
- Keep the explanation student-friendly.
"""


    try:

        answer = generate_ai(
            prompt
        )


        if answer:

            return jsonify({

                "ok": True,

                "answer":
                    answer,

                "source":
                    "ai"

            })


    except Exception as exc:

        app.logger.warning(
            "AI doubt error: %s",
            exc
        )


    return jsonify({

        "ok": True,

        "source":
            "fallback",

        "answer":
            "AI is not configured on this deployment yet. "
            "Add GEMINI_API_KEY in Render Environment Variables "
            "and reload SamStudy."

    })


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return jsonify({

        "ok": True,

        "firebase_admin":
            firebase_ready,

        "ai":
            bool(
                os.getenv(
                    "GEMINI_API_KEY"
                )
            )

    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
