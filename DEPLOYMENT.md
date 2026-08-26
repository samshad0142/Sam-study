# SamStudy Render Deployment

## Service

Runtime: Python

Build:
```text
pip install -r requirements.txt
```

Start:
```text
gunicorn app:app --workers 2 --threads 4 --timeout 180
```

## Required environment variables

```text
SECRET_KEY=<long random value>
ADMIN_EMAIL=samshad0142@gmail.com
ADMIN_PASSWORD=<developer password>
GEMINI_API_KEY=<Google AI key>
GEMINI_MODEL=gemini-2.5-flash
```

## Optional Firebase environment variables

```text
FIREBASE_API_KEY=
FIREBASE_AUTH_DOMAIN=
FIREBASE_PROJECT_ID=
FIREBASE_STORAGE_BUCKET=
FIREBASE_MESSAGING_SENDER_ID=
FIREBASE_APP_ID=
FIREBASE_SERVICE_ACCOUNT_JSON_B64=
```

After deployment open `/health`. It should return JSON showing `ok: true`. Open `/` for the real SamStudy web UI.
