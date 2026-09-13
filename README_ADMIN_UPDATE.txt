AI Library Assistant - Admin Portal Update

Files in this package:
- app.py: backend with admin borrow/return APIs, analytics, AI activity logging, and settings.
- templates/admin_dashboard.html: complete admin portal UI.
- templates/admin-students.html: existing student management page.
- templates/manage-books.html: existing book management page.
- static/script.js: existing shared script.
- static/style.css: existing shared stylesheet.

IMPORTANT:
1. Do NOT delete, rename, recreate, or replace database.db.
2. Backup your current app.py before replacing it.
3. Put app.py in C:\Libraryagent\app.py.
4. Put admin_dashboard.html and admin-students.html in templates\.
5. Put manage-books.html in templates\.
6. Put script.js and style.css in static\.
7. Restart Flask.

The backend automatically creates these additional tables if they do not exist:
- library_settings
- ai_activity

Existing books, students and borrowings are preserved.
Default settings remain 3 active books and 14 borrowing days.
