WASTE SETU - FINAL HACKATHON PROJECT PACKAGE
============================================

IMPORTANT
---------
This package does not contain your private backend/.env file, MongoDB credentials,
OpenRouter key, or Python virtual environment. Keep your existing .env and venv safe.
Do not upload .env to GitHub.

WHAT IS INCLUDED
----------------
- Existing Waste Setu frontend pages, images, styles and language files.
- Domestic household lot workflow (kept separate from non-domestic portals).
- Portal-isolated non-domestic workflow API: lots, collector requests/acceptance,
  same-portal recycler requests/acceptance, price offers/acceptance, invoices.
- Collector/recycler role dashboard.
- MongoDB persistence for lots, offers, requests, passport history and invoices.
- OpenRouter-backed chatbot and browser speech input/output widget on all HTML pages.
- Authentication fix: canonical portal/role matching, clearer account mismatch errors,
  bcrypt/passlib compatible dependency versions and password byte-length validation.
- Relative assistant asset paths, so Live Server works on ports such as 5500/5501/5502.

INSTALLATION ON WINDOWS / VS CODE
---------------------------------
1. Back up your current setu folder first.
2. Extract this ZIP. The project folder is setu/frontend-html.
3. Copy/replace the extracted frontend-html folder contents into your working
   C:\Users\pranav\Downloads\setu\frontend-html folder, preserving subfolders.
4. Keep your own backend/.env. Do NOT replace it with .env.example.
5. Open PowerShell in:
   C:\Users\pranav\Downloads\setu\frontend-html\backend
6. Activate your existing venv, or create it if you do not have one:
   python -m venv venv
   .\venv\Scripts\Activate.ps1
7. Install the pinned requirements:
   python -m pip install --upgrade pip
   pip install -r requirements.txt
8. Check backend/.env. It must contain valid single-line entries, for example:
   MONGODB_URI=mongodb+srv://...your real URI...
   DATABASE_NAME=e-wastesetu
   JWT_SECRET=...your existing long secret...
   OPENROUTER_API_KEY=...your real OpenRouter key...
   OPENROUTER_MODEL=openrouter/free
   Do not type angle-bracket placeholders into the real .env. If a value contains
   special characters, keep the complete value on one line and quote it when needed.
9. Start the API from the backend folder:
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
10. Open the frontend-html folder in VS Code. Right-click its index.html and choose
    Open with Live Server. Use the same root folder for every page.
11. API docs: https://waste-setuu.onrender.com/docs

AUTHENTICATION NOTES
--------------------
- Register each account with the intended portal and role.
- The same email/phone is unique across the users collection. A 409 means it already
  exists; use Login rather than registering it again.
- Login now verifies email/password first, then reports the stored portal/role if the
  account is being opened from the wrong login page.
- If the password was created using a broken/incompatible old bcrypt install, reset
  that account's password through a supported reset process; do not delete MongoDB
  users or manually edit password_hash.

WORKFLOW SEPARATION
-------------------
- Domestic household lots stay in /api/domestic and are not shown in non-domestic
  collector/recycler workflows.
- Non-domestic workflow queries always filter by the authenticated portal. E-waste
  collectors/recyclers cannot see battery, plastic, paper, metal, organic, rubber/tyre,
  or oil/chemical lots.
- A collector can request a lot; its owner accepts a collector. The assigned collector
  can request a recycler only from the same portal. That recycler can then accept.
- Connected parties can negotiate. The accepted offer becomes the agreed price.
- Invoice generation requires an agreed price. Invoice status is Generated, not Paid;
  no live UPI/bank payment verification gateway is configured in this prototype.

CHAT + VOICE ASSISTANT
---------------------
- Assistant appears at bottom-right on all HTML pages.
- OpenRouter key is read only by the backend; never put it in frontend JS.
- Microphone requires browser permission and Chrome/Edge speech-recognition support.
- Speech output uses the browser's installed voices.

TEST BEFORE PRESENTING
----------------------
1. Open /docs and confirm the API starts and MongoDB connects.
2. Register a new test account for one portal/role.
3. Log in with the same portal/role and confirm redirect to role-dashboard.html.
4. Create a lot and confirm it appears in MongoDB e-wastesetu.lots.
5. Log in as a collector in that same portal; request the lot.
6. Log back in as owner; accept the collector request.
7. Log in as collector; request a same-portal recycler.
8. Log in as that recycler; accept the requested lot.
9. Send and accept a price offer; generate invoice; check e-wastesetu.invoices.
10. Confirm another portal cannot see the lot.
11. Open the assistant, send a text message, then test microphone and read-aloud.

LIMITATIONS TO STATE HONESTLY IN THE HACKATHON
----------------------------------------------
- This package has not been run against your private MongoDB/OpenRouter credentials.
- Browser speech recognition depends on the browser and device.
- Invoice creation is persisted; real payment collection/verification is not integrated.
- Collector/recycler portal availability depends on registered users existing in that
  same portal. Some portal roles (e.g. metal) may need an upstream lot-creator account
  added if the intended card workflow requires one.
