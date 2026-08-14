# SamStudy — Fresh Setup

## What is included
- Responsive SamStudy educational platform UI
- Sky-blue + black dark theme with light/dark mode
- Animated 3D-style SS branding
- 1st Year / 2nd Year / 3rd Year / 4th Year batch sections
- Year → subject → unit-wise notes structure
- Notes download support
- Developer/admin-protected batch and content management endpoints
- Firebase authentication hooks for Google/Email/Phone
- AI Quiz flow: class → level → exam → subject
- AI Doubt Solver endpoint
- Motivation quote by Sam Malik
- YouTube: Sam_malik77
- Instagram: Sam_shad132
- Gmail: Samshad0142@gmail.com
- Render deployment configuration
- No Node/npm build step; Render uses Python + Gunicorn

## IMPORTANT: Firebase login
The earlier `auth/api-key-not-valid` error is caused by an incorrect Firebase Web App configuration.
Do NOT invent an API key.

In Firebase Console, create/select the Web App and copy the exact values into Render Environment Variables:
- FIREBASE_API_KEY
- FIREBASE_AUTH_DOMAIN
- FIREBASE_PROJECT_ID
- FIREBASE_STORAGE_BUCKET
- FIREBASE_MESSAGING_SENDER_ID
- FIREBASE_APP_ID

For secure server-side admin access also set:
- FIREBASE_SERVICE_ACCOUNT_JSON
- ADMIN_EMAIL=samshad0142@gmail.com

Never commit a Firebase service-account JSON file or Gemini API key to GitHub.

## AI
Set:
- GEMINI_API_KEY
- GEMINI_MODEL=gemini-2.5-flash

The frontend calls the server AI endpoints, so the Gemini secret is not exposed in browser code.

## Render
Use:
Build Command: `pip install -r requirements.txt`
Start Command: `gunicorn app:app`
Health Check: `/health`

This project intentionally has no npm/node build command, avoiding the common Error 127 caused by missing commands.

## GitHub upload
Extract this ZIP first. Upload the extracted project contents to the root of:
`samshad0142/Sam-study`

Do not upload the ZIP as the only repository file.

## Final owner links
YouTube: https://youtube.com/@sam_malik77
Instagram: https://instagram.com/Sam_shad132
Email: samshad0142@gmail.com

The included `preview.html` can be opened directly to inspect the visual layout without waiting for Firebase configuration.
