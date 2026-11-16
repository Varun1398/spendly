# Spec: Add Expense

## Overview
Users can currently see expenses on the profile page but can only get data in via the demo seed. This step replaces the `/expenses/add` placeholder with a real form: a logged-in user enters an amount, category, date and optional description, the server validates it, inserts it into `expenses` scoped to their user id, and redirects to the profile page with a success flash. It is the first write path for expenses and unlocks the edit (Step 8) and delete (Step 9) steps.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`)
- Step 3 — Login and logout (`session["user_id"]`)
- Step 4 — Profile page design (`profile.html`, "Add expense" empty-state link, `profile.css`)
- Step 5/6 — Profile filters (`get_categories`, summary and list must reflect new rows)

## Routes
- `GET /expenses/add` — render the add-expense form (date defaults to today) — logged-in
- `POST /expenses/add` — validate and insert the expense, flash success, redirect to `/profile` — logged-in

Both methods replace the existing placeholder `add_expense` view (same endpoint name, so `url_for('add_expense')` keeps working). Anonymous users are flashed "Please sign in to add an expense." and redirected to `/login`. Leave the edit/delete placeholders untouched.

## Database changes
No database changes. The existing `expenses` table (`user_id`, `amount REAL NOT NULL`, `category TEXT NOT NULL`, `date TEXT NOT NULL`, `description TEXT`, `created_at`) is sufficient. Add one helper to `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — parameterised INSERT, returns the new id

## Templates
- **Create:** `templates/add_expense.html` — form with amount, category, date, description; inline error message; re-fills submitted values on error; cancel link back to profile
- **Modify:**
  - `templates/profile.html` — add an "Add expense" button/link in the header or Recent expenses card (the empty-state link already exists)
  - `templates/base.html` — only if needed to add an "Add expense" navbar link for logged-in users (avoid disturbing the uncommitted analytics nav work if still present)

## Files to change
- `app.py` — implement `add_expense` (GET + POST), add `EXPENSE_CATEGORIES` constant and validation helper; import `create_expense`
- `database/db.py` — add `create_expense`
- `templates/profile.html` — add entry-point link
- `static/css/style.css` or `static/css/profile.css` — only if shared form styles are not already available

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — form-specific styles loaded via the `head` block
- `tests/test_add_expense.py` — auth, validation, insert and redirect tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate user input into SQL
- Passwords hashed with werkzeug (no password handling is changed; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the placeholder route; do not add a duplicate route
- Take `user_id` only from `session`, never from the form
- Fixed category list: Food, Transport, Bills, Health, Entertainment, Shopping, Other (matches seed data); reject any category not in the list
- Amount: parse with `Decimal`/`float`, must be a finite number > 0, at most 2 decimal places, reasonable upper bound (e.g. ≤ 10,000,000); reject `nan`/`inf`/blank/non-numeric
- Date: must be a valid `YYYY-MM-DD` (reuse `_parse_date`), not in the future
- Description: optional, stripped, max 200 chars; store `NULL` when empty
- On validation error re-render the form with status 200, an error message and previously entered values; do not insert
- On success use Post/Redirect/Get: flash "Expense added." (category `success`) and redirect to `profile`
- Keep Jinja autoescaping on for echoed values
- Existing tests and `/profile/summary` JSON contract must keep passing

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login` with a flash message; a POST while logged out inserts nothing
- [ ] Logged in, `/expenses/add` shows a form with amount, category (dropdown of the 7 categories), date (pre-filled with today) and description
- [ ] Submitting valid data redirects to `/profile` with an "Expense added." flash, and the new expense appears at the top of Recent expenses
- [ ] Profile total, count and category breakdown update to include the new expense
- [ ] The new row in `spendly.db` has the logged-in user's `user_id`
- [ ] Blank, zero, negative, non-numeric, `nan`/`inf` or >2-decimal amounts show an error and insert nothing
- [ ] An invalid category (e.g. tampered form value) shows an error and inserts nothing
- [ ] An invalid or future date shows an error and inserts nothing
- [ ] A description over 200 characters shows an error; an empty description saves as NULL
- [ ] After any validation error, the previously entered values remain in the form
- [ ] An "Add expense" link is reachable from the profile page, and the empty-state link works
- [ ] A new user with no expenses can add their first one and see it on the profile page
- [ ] HTML in the description (e.g. `<script>`) is displayed escaped, not executed
- [ ] `pytest tests/test_add_expense.py` passes
