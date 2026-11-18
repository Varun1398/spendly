# Spec: Edit Expense

## Overview
Users can add expenses (Step 7) but cannot correct a mistake. This step replaces the `/expenses/<id>/edit` placeholder with a real edit form: a logged-in user opens a pre-filled form for one of their own expenses, changes the amount, category, date or description, and the server validates it with the same rules as the add form and updates the row. Ownership is enforced so users can never view or modify someone else's expense. It is the update path of the expense CRUD and leads into delete (Step 9).

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`)
- Step 3 — Login and logout (`session["user_id"]`)
- Step 4 — Profile page design (`profile.html` Recent expenses list)
- Step 7 — Add expense (`_validate_expense`, `EXPENSE_CATEGORIES`, `add_expense.html`, `add_expense.css`)

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the expense's current values — logged-in, owner only
- `POST /expenses/<int:id>/edit` — validate and update the expense, flash success, redirect to `/profile` — logged-in, owner only

Both methods replace the existing placeholder `edit_expense` view (same endpoint name, so `url_for('edit_expense', id=...)` works). Anonymous users are flashed "Please sign in to edit an expense." and redirected to `/login`. If the expense does not exist or belongs to another user, return 404 (do not reveal which). Leave the delete placeholder untouched.

## Database changes
No database changes. Add two helpers to `database/db.py`:
- `get_expense(expense_id, user_id)` — parameterised SELECT of `id, amount, category, date, description` filtered by both `id` and `user_id`; returns a row or `None`
- `update_expense(expense_id, user_id, amount, category, date, description)` — parameterised UPDATE with `WHERE id = ? AND user_id = ?`; returns `True` if a row was updated (`cursor.rowcount == 1`), else `False`

## Templates
- **Create:** none (reuse the add-expense form)
- **Modify:**
  - `templates/add_expense.html` — make the form reusable for edit: heading, submit label ("Save changes" vs "Add expense") and form `action` driven by variables passed from the view; cancel link still goes to profile
  - `templates/profile.html` — add an "Edit" link per row in Recent expenses pointing to `url_for('edit_expense', id=e.id)`

## Files to change
- `app.py` — implement `edit_expense` (GET + POST); generalise `_render_expense_form` to accept the form title/action/submit label; reuse `_validate_expense`; import `get_expense`, `update_expense`; `abort` from flask
- `database/db.py` — add `get_expense`, `update_expense`
- `templates/add_expense.html` — parametrise heading/action/button
- `templates/profile.html` — per-row Edit link
- `static/css/profile.css` — style the Edit link (only if existing styles are insufficient)

## Files to create
- `tests/test_edit_expense.py` — auth, ownership, validation, update and redirect tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate user input into SQL
- Passwords hashed with werkzeug (no password handling is changed; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the placeholder route; do not add a duplicate route
- Take `user_id` only from `session`, never from the form; every SELECT/UPDATE must filter on both expense id and `user_id`
- Reuse `_validate_expense` unchanged so add and edit share identical rules (amount, category, date not in future, description ≤ 200, NULL when empty)
- Do not reuse `add_expense.html` by copy-paste; one template serves both flows
- Pre-fill the amount without float artefacts (e.g. `12.5` shows as `12.50`)
- On validation error re-render with status 200, an error message and the submitted values; do not update
- On success use Post/Redirect/Get: flash "Expense updated." (category `success`) and redirect to `profile`
- Editing must not change `user_id` or `created_at`
- Keep Jinja autoescaping on for echoed values
- Existing tests, the add-expense flow and the `/profile/summary` JSON contract must keep passing

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login` with a flash message; a POST while logged out changes nothing
- [ ] Each row in Recent expenses on the profile page has an Edit link that opens that expense's edit form
- [ ] The edit form is pre-filled with the expense's current amount (2 decimals), category, date and description
- [ ] Submitting valid changes redirects to `/profile` with an "Expense updated." flash, and the row shows the new values
- [ ] Profile total, count and category breakdown reflect the edited values (including a changed category)
- [ ] Requesting or POSTing to another user's expense id returns 404 and leaves that row unchanged
- [ ] Requesting a non-existent expense id returns 404
- [ ] Blank, zero, negative, non-numeric, `nan`/`inf` or >2-decimal amounts show an error and leave the row unchanged
- [ ] An invalid category (tampered form value) shows an error and leaves the row unchanged
- [ ] An invalid or future date shows an error and leaves the row unchanged
- [ ] A description over 200 characters shows an error; clearing the description saves it as NULL
- [ ] After a validation error the submitted values remain in the form
- [ ] The add-expense page still works and shows its original heading and button label
- [ ] HTML in the description (e.g. `<script>`) is displayed escaped, not executed
- [ ] `pytest tests/test_edit_expense.py` passes
