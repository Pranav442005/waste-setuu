WASTE SETU - HACKATHON WORKFLOW UPDATE
=====================================

This ZIP is based on the project you uploaded. Existing landing pages, waste-card pages,
logos, styles and authentication page designs are retained. A role-specific workspace has
been added for non-domestic portal accounts.

IMPORTANT: The original .env files are intentionally not included in this ZIP.
Keep your local backend/.env and restore its existing MongoDB URI and JWT secret.
Add OPENROUTER_API_KEY and OPENROUTER_MODEL to that same file. Never commit secrets.

WHAT WAS ADDED
--------------
1. Portal-isolated workflow API at /api/workflow.
2. Non-domestic provider lot creation with expectedPrice (INR), saved in MongoDB `lots`.
3. Collector available-lot list is filtered by the JWT portal.
4. Lot owners can accept collector requests.
5. Collector can request a recycler selected from the same portal only.
6. Recycler available lots show only lots requested from that recycler account.
7. Connected lot parties can send price offers and accept offers.
8. Agreed price is stored on the lot.
9. Invoice records are stored in MongoDB `invoices`; invoice ID is saved back to the lot.
10. Role-specific dashboard page: pages/role-dashboard.html.
11. Existing assistant JS is added to all HTML pages; voice input/output use browser speech APIs.
12. Domestic auth lookup now checks the actual token role, allowing household and administration.

PORTAL ISOLATION
----------------
Every workflow query and action includes the portal from the verified JWT. E-waste accounts
cannot view or negotiate battery/plastic/paper lots. Domestic lots remain on the separate
/api/domestic routes and are not exposed to non-domestic collectors or recyclers.

INSTALL
-------
1. Extract the ZIP and open `setu/frontend-html` in VS Code.
2. Preserve your existing `backend/.env`. Do not replace it with `.env.example`.
3. Add these variables to backend/.env:
   OPENROUTER_API_KEY=your-key
   OPENROUTER_MODEL=openrouter/free
4. In PowerShell:
   cd <your-project>\backend
   ..\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
5. Serve frontend-html with VS Code Live Server.
6. Log in through each portal's existing auth page. Non-domestic accounts redirect to
   pages/role-dashboard.html. Household and administration retain their existing dashboards.
7. Verify records in MongoDB Compass:
   database `e-wastesetu` -> collections `lots` and `invoices`.

API ROUTES
----------
POST   /api/workflow/lots
GET    /api/workflow/lots/mine
GET    /api/workflow/lots/available
POST   /api/workflow/lots/{lot_id}/collector-request
POST   /api/workflow/lots/{lot_id}/collector-accept/{collector_id}
GET    /api/workflow/collectors/recyclers
POST   /api/workflow/lots/{lot_id}/recycler-request
POST   /api/workflow/lots/{lot_id}/recycler-accept
POST   /api/workflow/lots/{lot_id}/offers
POST   /api/workflow/lots/{lot_id}/offers/{offer_id}/accept
GET    /api/workflow/transactions
POST   /api/workflow/lots/{lot_id}/invoice
GET    /api/workflow/dashboard
POST   /api/assistant/chat

IMPORTANT WORKFLOW NOTES
------------------------
- Lot creators enter an expected price at creation.
- Negotiation offers and accepted agreed price are stored on the lot document.
- Invoice generation requires an agreed price; it creates a MongoDB invoice record.
- Invoice status is "Generated", not "Paid". This implementation does not claim to process
  real payments or verify bank/UPI transfers.
- Domestic household flow remains separate and does not use commercial negotiations.
- Metal portal currently has only metal/non-metal collector and recycler roles in the
  uploaded authentication configuration; no separate upstream metal producer role exists.
  The role dashboard follows the account roles already present in your project.
- Organic portal has no recycler role in the uploaded account configuration; organic
  collector/recycler features are limited to roles configured by the original project.
- Voice microphone requires browser permission and support (Chrome/Edge recommended).
- OpenRouter and MongoDB must be configured with valid credentials for live operation.

TESTS PERFORMED
---------------
- Python syntax compilation passed for the changed backend modules.
- JavaScript syntax check passed for role-dashboard.js and the assistant script.
- This environment cannot validate your private MongoDB connection, OpenRouter key,
  browser microphone permission, or end-to-end transactions. Test those on your laptop.
