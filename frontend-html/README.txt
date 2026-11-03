WASTE SETU HTML FRONTEND — STAGE 1

This is a separate, static HTML/CSS/JavaScript frontend starter.
It does not modify your existing backend or public/ folder.

INSTALL:
1. Copy the folder named waste_setu_html_stage1 into your project root.
2. Rename it to: frontend-html
3. Keep the structure:
   frontend-html/index.html
   frontend-html/assets/css/styles.css
   frontend-html/assets/js/config.js
   frontend-html/assets/js/main.js

IMAGE PATHS:
Place your permitted banner images here:
frontend-html/images/waste-management-1.jpg
frontend-html/images/waste-management-2.jpg
frontend-html/images/waste-management-3.jpg
If these files are absent, the hero still displays its green gradient background.

EXPRESS:
In server/src/index.ts, after all API routes and before the catch-all route, add:
const htmlFrontendDir = path.resolve(__dirname, '../../frontend-html');
app.use(express.static(htmlFrontendDir));

Then make the catch-all serve:
res.sendFile(path.join(htmlFrontendDir, 'index.html'));

Do not remove or replace API routes. Do not add a second app.listen().
Do not expose .env, MongoDB credentials, or secrets to browser JavaScript.

NOTE:
The homepage links to page files that will be created in Stage 2.
The carousel and layout work now; language translation, admin-managed uploads,
and API-backed forms/dashboards are later stages. The statistics are user-supplied
prototype figures and should be verified before being represented as official data.
