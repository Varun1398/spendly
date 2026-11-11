# Spec: Registration

## Overview
Turn the static `/register` page into a working sign-up flow. A visitor submits name, email and password; the server validates the input, hashes the password with werkzeug, inserts a row into `users`, On success the user is shown with a success message and then redirects to the login page. This is the first step that writes user data and is the prerequisite for login/logout (Step 3) and every logged-in feature after it.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`).

## Routes
- `GET /register` — render the registration form (already exists) — public
- `POST /register` — validate form, create user, redirect to `/login` on success; re-render form with an error message on failure — public

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE, `password_hash`, `created_at`) in `database/db.py` is sufficient.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — form `action` should use `url_for('register')`; re-populate `name` and `email` inputs after a validation error (never the password); keep the existing `{% if error %}` block.
  - `templates/login.html` — display a flashed/success message ("Account created, please sign in") if present.

## Files to change
- `app.py` — import `request`, `redirect`, `url_for`, `flash`; set `app.secret_key`; change `/register` to accept `GET` and `POST` and implement the handler.
- `database/db.py` — add helper `create_user(name, email, password)` and `get_user_by_email(email)` (parameterised queries, password hashed with werkzeug).
- `templates/register.html`
- `templates/login.html`
- `static/css/style.css` — only if a success-message style is needed (use CSS variables).

## Files to create
- `tests/test_registration.py` — pytest tests for the registration flow.

## New dependencies
No new dependencies (pytest and pytest-flask already in `requirements.txt`).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Normalise email (`strip().lower()`) before validation and storage
- Validation (server-side): name non-empty; email contains a valid-looking address; password at least 8 characters; duplicate email rejected with a friendly message (catch `sqlite3.IntegrityError`, do not rely on a pre-check alone)
- Do not reveal internal errors to the user; always close DB connections
- Secret key must come from an environment variable with a dev fallback, not a hardcoded production secret
- Replace the existing `/register` route; do not add a duplicate

## Definition of done
- [ ] `GET /register` renders the form with name, email and password fields
- [ ] Submitting valid data creates a row in `users` with a hashed (not plaintext) `password_hash`
- [ ] After successful registration the browser is redirected to `/login` and a success message is shown
- [ ] Submitting an email that already exists (including `demo@spendly.com`, case-insensitive) re-renders the form with an error and creates no new row
- [ ] Password shorter than 8 characters shows an error and creates no user
- [ ] Empty name or invalid email shows an error and creates no user
- [ ] After an error, name and email fields keep their values; password field is empty
- [ ] App starts without errors and existing pages (`/`, `/login`, `/terms`, `/privacy`) still work
- [ ] `pytest` passes, including tests for success, duplicate email, short password and missing fields
