# SamStudy — Final Fresh Setup

This is the final SamStudy Flask + Firebase setup intended to replace the previous project completely.

## Final design
- Sky-blue + black/white visual system.
- Light mode: white + sky-blue + dark text.
- Night mode: deep black/navy + white + sky-blue.
- Animated 3-D **SS** brand/logo with floating/orbit motion.
- Larger, cleaner page proportions; cards stay in rows on desktop/tablet and compact 2-column layout on phones.
- Separate **1st Year / 2nd Year / 3rd Year / 4th Year** B.Tech sections.
- No fake 01/02/03/04 feature strip.
- Motivation quote with **Sam Malik**.
- YouTube channel directly below the motivation quote: `@sam_malik77`.

## Features
- Firebase Email/Password authentication.
- Firebase Google authentication using mobile-friendly redirect.
- Create account + password reset.
- Developer account: `samshad0142@gmail.com`.
- Developer-only `/admin` dashboard.
- Developer can create batches for years 1–4.
- Developer can upload notes/content and select year + subject + unit while uploading.
- Students can filter notes by year/subject/unit and download uploaded files.
- AI quiz: class/year → level → exam → relevant subject → fresh quiz.
- AI doubt solver: direct question → step-by-step answer.
- 3-D learning page.

## IMPORTANT — fix the old Firebase `auth/api-key-not-valid` error
The previous error was not caused by the login button. It means the Firebase Web App configuration being served to the browser was invalid.

This package does **not** guess or hard-code your Firebase API key. Configure the exact values from your Firebase Web App.

### Firebase Web App values
Firebase Console → Project settings → Your apps → Web app → SDK setup and configuration.

Set these Render environment variables:

- `FIREBASE_API_KEY`
- `FIREBASE_AUTH_DOMAIN`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_MESSAGING_SENDER_ID`
- `FIREBASE_APP_ID`

### Firebase Authentication
Authentication → Sign-in method:
- Enable Email/Password.
- Enable Google.

Authentication → Settings → Authorized domains:
- Add your exact Render domain, for example `sam-study.onrender.com`.

### Firebase Admin server access
Create a Firebase service-account JSON from:
Project settings → Service accounts → Generate new private key.

Put the complete JSON into Render as:
- `FIREBASE_SERVICE_ACCOUNT_JSON`

Never upload the service-account JSON to GitHub.

### Firestore
Create Firestore Database. The app uses:
- `batches`
- `notes`

The server checks the Firebase ID token and then checks the email against `ADMIN_EMAIL`. Do not remove that server-side check.

## AI setup
Create a Gemini API key and set:
- `GEMINI_API_KEY`

Optional:
- `GEMINI_MODEL` (default: `gemini-2.5-flash`)

The quiz and doubt APIs are server-side. Do not put the Gemini key in HTML or JavaScript.

## Render setup from zero
1. Upload the **contents** of this package to the root of your GitHub repository.
2. In Render create a new Web Service from that GitHub repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add the Firebase and Gemini environment variables above.
6. Deploy.
7. Open `/health`. It should return JSON with `ok: true`.
8. Add the final Render domain to Firebase Authorized Domains.
9. Open `/login` and test Email/Password, Create Account and Google.
10. Login as `samshad0142@gmail.com`, then open `/admin` to create batches and upload content.

## Notes upload workflow
Developer → `/admin` → choose Year → Subject → Unit → upload file.
Students → `/notes` → choose Year → Subject → Unit → Download.

## Quiz workflow
Quiz → choose class/year → choose level → choose exam → choose relevant subject → Generate Fresh Quiz.
Each generation is a new request to the AI engine.

## Important honesty note
No package can make Firebase login work without the correct Firebase project configuration. The code is prepared for the correct configuration, but the real Firebase Web App values and service account belong to your Firebase project and must be supplied in Render.
