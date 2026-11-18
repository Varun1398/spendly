# Spec: Delete Expense

## Overview
Users can add expenses (Step 7) but cannot remove one entered by mistake. This step replaces the `/expenses/<id>/delete` placeholder with a real, safe delete flow: each row in the profile's Recent expenses table gets a "Delete" action that leads to a confirmation page showing the expense; confirming sends a POST that removes the row (only if it belongs to the logged-in user), flashes a success message and redirects back to the profile. Deletion never happens on a plain GET, so links, prefetching or crawlers cannot destroy data.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`)
- Step 3 — Login and logout (`session["user_id"]`)
- Step 4 — Profile page design (`profile.html`, Recent expenses table, `profile.css`)
- Step 5/6 — Profile filters (summary, breakdown and list must reflect the removal)
- Step 7 — Add expense (`add_expense.html` / `add_expense.css` form styling to reuse; Step 8 edit is not required)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the expense's date, description, category and amount, with Confirm and Cancel — logged-in (owner only)
- `POST /expenses/<int:id>/delete` — delete the expense, flash "Expense deleted." (category `success`), redirect to `/profile` — logged-in (owner only)

Both methods replace the existing placeholder `delete_expense` view (same endpoint name, so `url_for('delete_expense', id=...)` keeps working). Anonymous users are flashed "Please sign in to delete an expense." and redirected to `/login`; a logged-out POST deletes nothing. If the expense does not exist or belongs to another user, respond with 404 (identical response for both cases so ids cannot be probed). Leave the edit placeholder untouched.

## Database changes
No database changes. Add two helpers to `database/db.py`:
- `get_expense(expense_id, user_id)` — parameterised `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`; returns the row or `None`
- `delete_expense(expense_id, user_id)` — parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`; commits and returns `True` if a row was deleted, else `False` (check `cursor.rowcount`)

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html`; confirmation card with the expense details, a `<form method="post">` Confirm (destructive style) button and a Cancel link back to the profile
- **Modify:** `templates/profile.html` — add an "Actions" column header and a "Delete" link per row in the Recent expenses table (`url_for('delete_expense', id=e['id'])`), including the mobile `data-label` stacked layout

## Files to change
- `app.py` — implement `delete_expense` (GET + POST, `methods=["GET", "POST"]`); import `get_expense` and `delete_expense` helper (alias to avoid clashing with the view name, e.g. `from database.db import delete_expense as remove_expense`)
- `database/db.py` — add `get_expense`, `delete_expense`
- `templates/profile.html` — add the Delete action column
- `static/css/profile.css` — style the action link and column using CSS variables

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css` — confirmation page styles loaded via the `head` block (only if `add_expense.css` cannot be reused)
- `tests/test_delete_expense.py` — auth, ownership, GET-does-not-delete, POST-deletes and redirect tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate user input into SQL
- Passwords hashed with werkzeug (no password handling is changed; never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the placeholder route; do not add a duplicate route
- Take `user_id` only from `session`, never from the form or query string
- Ownership must be enforced in the SQL (`WHERE id = ? AND user_id = ?`), not only in Python
- A GET request must never modify data; only POST deletes
- Missing and not-owned expenses both return 404 (`abort(404)`)
- Use Post/Redirect/Get: on success flash "Expense deleted." (category `success`) and `redirect(url_for("profile"))`
- Keep Jinja autoescaping on for the echoed description and category
- Close DB connections in `finally`, matching existing helpers
- Existing tests, the `/profile/summary` JSON contract and add-expense behaviour must keep passing

## Definition of done
- [ ] Logged out, visiting `/expenses/1/delete` redirects to `/login` with a flash message; a logged-out POST deletes nothing
- [ ] Logged in, every row in Recent expenses on `/profile` has a "Delete" link, and it also works in the mobile stacked layout
- [ ] Clicking Delete opens a confirmation page showing that expense's date, description, category and amount
- [ ] Opening the confirmation page (GET) does not remove the expense; clicking Cancel returns to `/profile` with the expense still present
- [ ] Clicking Confirm redirects to `/profile` with an "Expense deleted." flash and the row is gone from `spendly.db`
- [ ] After deletion, the profile total, count and category breakdown no longer include the expense, and `/profile/summary` reflects the change
- [ ] Deleting the last expense in a category removes that category from the breakdown and the filter dropdown
- [ ] Requesting `/expenses/<id>/delete` (GET or POST) for another user's expense returns 404 and that expense remains in the database
- [ ] Requesting a non-existent id returns 404
- [ ] Deleting an expense that was already deleted (e.g. back button, second POST) returns 404 without error or a server crash
- [ ] A description containing `<script>` is displayed escaped on the confirmation page
- [ ] Other expenses and other users' data are unaffected by a delete
