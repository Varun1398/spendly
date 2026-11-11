# Spec: Login and Logout

## Overview
Turn the static `/login` page into a working sign-in flow and replace the `/logout` placeholder with a real session teardown. A visitor submits email and password; the server looks up the user, verifies the password hash with werkzeug, stores the user id in the Flask session and redirects to the app. Logout clears the session. This step introduces authentication state, which every later logged-in feature (profile, expenses CRUD) depends on.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()` demo user).
- Step 2 — Registration (`create_user`, `get_user_by_email`, `app.secret_key`, flash messaging on `/login`).

## Routes
- `GET /login` — render the sign-in form (exists); redirect to `/profile` if already logged in — public
- `POST /login` — validate credentials, set `session["user_id"]` and `session["user_name"]`, redirect to `/profile`; re-render form with a generic error on failure — public
- `GET /logout` — clear the session, flash "You have been signed out.", redirect to `/login` — logged-in (harmless if not logged in: simply redirects to `/login`)

## Database changes
No database changes. `users` already has `email` (UNIQUE) and `password_hash`; `get_user_by_email()` in `database/db.py` is sufficient.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — form `action` uses `url_for('login')`; re-populate the `email` input after a failed attempt (never the password); keep existing flash/`error` blocks.
  - `templates/base.html` — navbar is session-aware: when `session.user_id` is set show the user's name/"Profile" link and a "Sign out" link (`url_for('logout')`); otherwise show "Sign in" and "Get started".

## Files to change
- `app.py` — import `session` and `check_password_hash`; implement `POST /login`; replace the `/logout` placeholder; redirect logged-in users away from `/login` and `/register`.
- `templates/login.html`
- `templates/base.html`
- `static/css/style.css` — only if the navbar needs a style for the signed-in state (use CSS variables).

## Files to create
- `tests/test_login_logout.py` — pytest tests for the login and logout flows.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use string formatting in SQL
- Passwords verified with werkzeug (`check_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Normalise email (`strip().lower()`) before lookup
- Use one generic error ("Invalid email or password.") for both unknown email and wrong password — do not reveal which was wrong
- Store only `user_id` (and display name) in the session; never the password hash
- Call `session.clear()` on logout and before setting a new session on login (prevents stale/fixated session data)
- Secret key continues to come from the `SECRET_KEY` env var with a dev fallback
- Replace the existing `/login` and `/logout` routes; do not add duplicates
- Redirect only to internal `url_for(...)` targets — no open redirect via a `next` parameter
- Leave other placeholder routes (`/profile`, `/expenses/...`) untouched; `/profile` remains a stub until Step 4

## Definition of done
- [ ] `GET /login` renders the form with email and password fields
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects to `/profile` and the navbar shows a signed-in state with a "Sign out" link
- [ ] Email matching is case-insensitive and ignores surrounding whitespace
- [ ] Wrong password shows "Invalid email or password." and no session is created
- [ ] Unknown email shows the same "Invalid email or password." message
- [ ] After a failed attempt the email field keeps its value; the password field is empty
- [ ] A user newly created via `/register` can sign in with the same credentials
- [ ] `GET /logout` clears the session, redirects to `/login`, and shows a "signed out" message; navbar returns to "Sign in" / "Get started"
- [ ] Visiting `/login` or `/register` while signed in redirects to `/profile`
- [ ] Session cookie contains no plaintext password or hash
- [ ] App starts without errors and `/`, `/register`, `/terms`, `/privacy` still work
- [ ] `pytest` passes, including tests for successful login, wrong password, unknown email, logout, and already-logged-in redirect
