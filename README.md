# SamStudy — Mobile-first final setup

This version keeps the SamStudy dark/light visual identity from the supplied reference and adds the requested functional sections without replacing the overall design language.

## Visual changes in this version
- Same dark navy + cyan/purple/teal/gold accent palette as the supplied reference.
- Mobile layout uses compact year cards and compact tool cards with the same icon proportions.
- Home / Batches / Quiz / Tests / Profile are fixed in the bottom mobile navigation.
- Notes, AI Doubt and 3-D remain available from the page/tool cards and desktop navigation.
- Light mode and dark mode persist using localStorage.
- Supplied `static/logo.png` is used in the header, hero 3-D logo, 3-D section and auth/profile UI.

## Functional fixes
- Login button changes to Profile after successful login.
- Hero Login/Sign up changes to Open Profile after login.
- Logout signs Firebase out and immediately restores the logged-out UI.
- Profile supports name, course, optional exam, Gmail verification status and changeable photo.
- Profile is saved to the server when Firebase Admin is configured; otherwise a device-local fallback keeps it saved.
- Notes have an in-page details modal plus download/external-link actions.
- 3-D modules open inside the page instead of navigating to an error page.
- AI doubt solver supports typed text, voice input and image upload through Gemini.
- AI quiz supports course, exam, subject, difficulty and question count with seen-question tracking.
- Real-exam test supports timed questions, marking, negative marking, per-question time and final analysis.
- Developer Console is available to emails listed in `ADMIN_EMAILS`.

## Render / Firebase / Gemini variables
See `.env.example` and `render.yaml`.

For live Google Login, server-side profile storage, admin content uploads and persistent AI quiz/test history, configure:
- Firebase Web config variables
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `ADMIN_EMAILS`
- `GEMINI_API_KEY`

## GitHub replacement order
If replacing files one at a time, use this order:
1. `templates/index.html`
2. `static/style.css`
3. `static/app.js`
4. `app.py`
5. `requirements.txt`
6. `render.yaml`
7. `.env.example`
8. `static/logo.png`

Do not delete the existing `data/` or `static/uploads/` directories if they contain your production content.

## Preview
Open `preview.html` from the project folder. It is a standalone mobile visual preview and does not require Firebase.

## Template structure
The UI is now modular. `templates/base.html` contains the shared shell; `templates/sections/` contains Home, Batches, Tools, Notes, Quiz, Tests, 3-D and Doubt; `templates/modals/` contains Login, Profile, Notes details and Developer Console; `templates/partials/` contains the header, footer and mobile bottom navigation.


## Final light-mode pass
- Batch year badges (`1st`, `2nd`, `3rd`, `4th`) have explicit light-mode contrast.
- Header brand/navigation, cards, forms, outputs, quiz/test content, modal text, bottom navigation, and placeholders receive explicit light-mode colors.
- Theme preference is restored before the main UI renders to reduce dark-mode flash.
- Theme button updates the browser `theme-color` meta tag.
- Standalone `preview.html` includes the same light-mode contrast protections.
- Existing dark design, 3-D logo treatment, card sizing, and mobile bottom navigation are preserved.
