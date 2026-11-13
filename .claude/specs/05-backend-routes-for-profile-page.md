# Spec: Backend Routes for Profile Page

## Overview
Step 4 built the profile page on top of three fixed, unfiltered queries. This step gives the profile page a proper backend: `/profile` accepts optional query-string filters (date range and category) that are validated on the server and applied to every query feeding the page (summary tiles, category breakdown, recent expenses), and a new read-only JSON route exposes the same summary data for the page (and later steps such as charts) to consume. Filtering is done in SQL with parameterised queries, scoped to the signed-in user. This sets up the data layer that the expense CRUD steps (7–9) will build on.

## Depends on
- Step 1 — Database setup (`users`, `expenses`, `get_db()`, `seed_db()`)
- Step 3 — Login and logout (`session["user_id"]`)
- Step 4 — Profile page design (`/profile`, `get_expense_summary`, `get_category_totals`, `get_recent_expenses`, `profile.html`)

## Routes
- `GET /profile` — existing route, extended: accepts optional `?from=YYYY-MM-DD&to=YYYY-MM-DD&category=<name>`; invalid or missing values are ignored (no 500s) and an invalid range (`from` > `to`) shows a flash error and falls back to unfiltered — logged-in
- `GET /profile/summary` — JSON `{total, count, top_category, categories: [{category, total, pct}]}` for the signed-in user, honouring the same filters — logged-in (signed-out requests get `401` JSON, not a redirect)

No other new routes. Leave the `/expenses/...` placeholder routes untouched.

## Database changes
No database changes. Existing `expenses` columns (`amount`, `category`, `date`, `user_id`) are sufficient; `date` is stored as ISO `YYYY-MM-DD` text so range comparison with `>=`/`<=` works.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — add a filter bar (from date, to date, category select, Apply and Clear controls) above the stat tiles, pre-filled from the current filters; show a "no expenses match these filters" empty state distinct from the "no expenses yet" state; list the active filter near the stat tiles

## Files to change
- `app.py` — extend `profile()` to parse/validate filters and pass them to the db helpers; add `profile_summary()` route; reuse `_with_percentages`
- `database/db.py` — add optional `date_from=None, date_to=None, category=None` params to `get_expense_summary`, `get_category_totals`, `get_recent_expenses`; add `get_categories(user_id)` returning the user's distinct categories for the filter dropdown
- `templates/profile.html` — filter bar and empty states (above)
- `static/css/profile.css` — filter bar styles (CSS variables only)
- `tests/test_profile.py` — extend with filter tests

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — build the WHERE clause from fixed fragments and pass values as parameters; never interpolate user input into SQL
- Passwords hashed with werkzeug (never select `password_hash` into a template or JSON response)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace/extend the existing `/profile` route; do not add a duplicate
- Scope every query by `session["user_id"]` — a user must only see their own data
- Aggregate in SQL (`SUM`, `COUNT`, `GROUP BY`), not in Python loops
- Validate `from`/`to` with `datetime.strptime(..., "%Y-%m-%d")`; validate `category` against the user's own categories, ignoring unknown values
- Existing helper signatures must stay backward compatible (new params optional) so current tests keep passing
- Filters must work via plain GET form submission with no JavaScript required
- Handle zero matching rows without errors (no division by zero)
- Keep Jinja autoescaping on for all echoed filter values

## Definition of done
- [ ] `/profile` with no query string looks and behaves exactly as before (demo user: 8 expenses, 400.24 total, top category Bills)
- [ ] `/profile?category=Food` shows only Food expenses and the tiles, breakdown and list all reflect that filter
- [ ] `/profile?from=2000-01-01&to=2000-01-31` shows the "no expenses match" empty state with zeros and no errors
- [ ] `from` and `to` each work on their own; bounds are inclusive
- [ ] `from` later than `to` shows a flash error and falls back to the unfiltered view
- [ ] Garbage values (`from=abc`, `category=<script>`, `category=Nope`) never cause a 500 and are ignored or escaped
- [ ] The filter bar is pre-filled with the active filters and Clear returns to `/profile`
- [ ] `GET /profile/summary` signed in returns JSON matching the page numbers for the same filters
- [ ] `GET /profile/summary` signed out returns `401` JSON
- [ ] A user can never see another user's data via filters or the JSON route
- [ ] The filter bar renders correctly at mobile (~375px) and desktop widths
- [ ] No hardcoded hex values in new CSS
- [ ] `/`, `/login`, `/register`, `/terms`, `/privacy` still work and the app starts without errors
- [ ] `pytest` passes, including new tests for each filter, invalid input, the JSON route (auth and shape) and data isolation
