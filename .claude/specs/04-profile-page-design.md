# Spec: Profile Page Design

## Overview
Replace the `/profile` placeholder with a real, designed profile page for the signed-in user. The page shows who the user is (name, email, member-since date) and a summary of their spending pulled from the `expenses` table: total spent, number of expenses, a per-category breakdown, and a list of recent expenses. It is the first logged-in page of Spendly and the landing target after login, so it establishes the visual language (cards, stat tiles, tables) that later expense CRUD steps will reuse.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `seed_db()` demo data).
- Step 2 — Registration (`create_user`, users exist to view).
- Step 3 — Login and logout (`session["user_id"]`, session-aware navbar).

## Routes
- `GET /profile` — render the profile page for the current user; redirect to `/login` if not signed in — logged-in

No other new routes.

## Database changes
No database changes. `users` (`name`, `email`, `created_at`) and `expenses` (`amount`, `category`, `date`, `description`, `user_id`) already provide everything needed. New read-only query helpers are added to `database/db.py` (see Files to change).

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; sections: profile header (avatar initial, name, email, member since), summary stat tiles (total spent, expense count, top category), category breakdown, recent expenses table, and an empty state when the user has no expenses.
- **Modify:**
  - `templates/base.html` — make the navbar user name a link to `url_for('profile')`.

## Files to change
- `app.py` — replace the `/profile` placeholder; require login; redirect signed-in users from `/login` and `/register`, and after successful login, to `url_for('profile')`.
- `database/db.py` — add `get_user_by_id(user_id)`, `get_expense_summary(user_id)` (total, count), `get_category_totals(user_id)` and `get_recent_expenses(user_id, limit=10)`.
- `templates/base.html` — navbar profile link.
- `static/css/style.css` — keep the nav user link visible on mobile; shared tokens/components only if needed (CSS variables).

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles, loaded via `{% block head %}`.
- `tests/test_profile.py` — pytest tests for the profile page.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (never select `password_hash` into the template context)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the existing `/profile` route; do not add a duplicate
- Scope every query by `session["user_id"]` — a user must only see their own data
- Aggregate in SQL (`SUM`, `COUNT`, `GROUP BY`), not in Python loops
- Keep Jinja autoescaping on for user-provided fields (name, email, description)
- Format amounts as currency with two decimals (₹)
- Layout must be responsive down to mobile width
- Leave the `/expenses/...` placeholder routes untouched
- Handle a user with zero expenses without errors (empty state, no division by zero)

## Definition of done
- [ ] Visiting `/profile` while signed out redirects to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` lands on `/profile`
- [ ] The header shows the user's name, email, and member-since date
- [ ] Total spent and expense count match the seeded demo data (8 expenses, 400.24 total, top category Bills)
- [ ] The category breakdown lists each category with its total, highest first, and bar percentages sum to 100
- [ ] Recent expenses are listed newest first with date, category, description, amount
- [ ] A newly registered user with no expenses sees an empty state and no errors
- [ ] A user never sees another user's expenses
- [ ] The navbar user name links to `/profile` and stays reachable on mobile
- [ ] The page renders correctly at mobile (~375px) and desktop widths
- [ ] No hardcoded hex values appear in the new CSS
- [ ] App starts without errors and `/`, `/login`, `/register`, `/terms`, `/privacy` still work
- [ ] `pytest` passes, including tests for auth redirect, demo data totals, empty state, and data isolation
