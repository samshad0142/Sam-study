# SamStudy — Complete Real Working Website

This repository keeps the SamStudy preview UI while replacing demo-only actions with working Flask APIs.

## Included

- Same dark/light visual system, 3D SamStudy background/logo and navigation from the selected preview.
- Batches → selected exam/course → batch → subjects → chapter → Notes / Lectures.
- AI Quiz with selectable question count, deselect-until-Next behavior and result analysis.
- AI Test with exam-pattern timing, answer changes until Final Submit, review/mark-for-review and auto-submit on timeout.
- Gemini AI doubt solving, including image questions.
- Downloadable AI doubt PDFs.
- Gemini-generated chapter-note PDFs.
- Gemini 3D scene generation rendered with Three.js.
- YouTube lecture search for the selected exam/course, subject and chapter.
- Optional uploaded-book verification flow for evidence-backed answers.
- Email/password login works through the included Flask backend immediately; Firebase Google/Phone auth can be enabled with Render environment variables.
- StudyShield web settings plus an Android companion that uses Usage Access + Accessibility Service for per-app daily limits.
- Developer panel for adding batches, resource URLs, books and content.

## Render deployment

1. Create a Python Web Service from this repository.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn app:app --workers 2 --threads 4 --timeout 180`
4. Add at least:
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
   - `GEMINI_API_KEY`
5. Optional Firebase variables enable Google/Phone authentication and Firebase-backed developer verification.

The default admin email is `samshad0142@gmail.com`. Set `ADMIN_PASSWORD` to the password you want for that developer account.

## Gemini

Set `GEMINI_API_KEY`. The default model is `gemini-2.5-flash`; it can be changed with `GEMINI_MODEL` if your Google AI project uses another supported model.

AI is called server-side so the Gemini key is never shipped to the browser.

## Firebase

For Google/Phone login, create a Firebase Web App and configure:

- `FIREBASE_API_KEY`
- `FIREBASE_AUTH_DOMAIN`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_MESSAGING_SENDER_ID`
- `FIREBASE_APP_ID`
- `FIREBASE_SERVICE_ACCOUNT_JSON_B64` for server-side ID-token verification

Email/password local login remains available even if Firebase is not configured.

## Android StudyShield

Open `android-studyshield` as a separate Android Studio project. Enable Usage Access and Accessibility, then set each app's daily limit. The Android project is intentionally kept inside this repository because it is a companion app, not a Python package.

A normal Android app cannot guarantee that the user cannot uninstall or force-stop it. Stronger tamper resistance requires device-owner/enterprise kiosk management.

## Important production note

The included SQLite database and uploaded files live on the service filesystem. For production-scale persistence on Render, attach a persistent disk or move users/content to a managed database/object store. Firebase is recommended when account persistence must survive redeploys.
