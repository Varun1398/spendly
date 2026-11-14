# Spec: Date Filter for Profile Page

## Overview
Step 5 added server-side `from`/`to`/`category` filtering and a basic filter bar with two raw date inputs. This step turns that into a proper date filter experience: one-click preset ranges (This month, Last month, Last 7 days, Last 30 days, This year, All time) rendered as plain links, the active preset highlighted, date inputs that constrain each other (`min`/`max`), and the selected category preserved when a preset is clicked. Presets are computed on the server relative to today, so the feature works with no JavaScript. No new data layer is needed — presets simply resolve to the existing `?from=&to=` query params.

## Depends on
- Step 1 — Database setup (`expenses.date` stored as ISO `YYYY-MM-DD`)
- Step 3 — Login and logout (`session["user_id"]`)
- Step 4 — Profile page design (`profile.html`, `profile.css`)
- Step 5 — Backend routes for profile page (`_parse_filters`, `/profile`, `/profile/summary`, existing filter bar)

## Routes
- `GET /profile` — existing route, no signature change. Continues to accept `?from=&to=&category=`; preset links are just pre-built URLs of this form — logged-in
- `GET /profile/summary` — unchanged — logged-in

No new routes. Leave the `/expenses/...` placeholder routes untouched.

## Database changes
No database changes. Existing `_expense_filter` already applies inclusive `date >= ? / date <= ?` bounds.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — add a preset row (chip links) above/inside the filter bar; mark the active preset with `aria-current="true"` and an active class; add `min`/`max` attributes to the From/To inputs; show the active date range as a human-readable label (e.g. "1 Nov 2026 – 14 Nov 2026") in the existing active-filter line

## Files to change
- `app.py` — add `_date_presets(today, filters)` helper returning a list of `{key, label, args, active}` for the template (`args` are the `url_for('profile', ...)` query params; `active` is computed from the current `filters`; "All time" is active when no dates are set); pass `presets` to `render_template` in `profile()`; keep `_parse_filters` behaviour unchanged
- `templates/profile.html` — preset chips and input constraints (above)
- `static/css/profile.css` — preset chip styles incl. active state (CSS variables only)
- `app.py` also: `nicedate` Jinja filter, and `_parse_date` now returns the canonical zero-padded ISO date

## Files to create
- `tests/test_date_filter.py` — preset, active-state, min/max and validation tests

## New dependencies
No new dependencies. Use the stdlib `datetime`/`calendar` only.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — no SQL changes expected; if any are made, never interpolate user input
- Passwords hashed with werkzeug (never expose `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace/extend the existing `/profile` route and filter bar; do not add duplicate routes or a second form
- Presets must be plain `<a href>` links built with `url_for('profile', **args)` — no JavaScript required
- Preset links must carry over the currently selected `category`, and must not carry over stale `from`/`to`
- "All time" preset clears `from`/`to` but keeps `category`
- Compute presets from `date.today()` on the server; pass `today` into the helper so it is unit-testable
- Month boundaries must be correct for 28/29/30/31-day months and year rollover (e.g. "Last month" in January → previous December)
- A preset is "active" only when the current valid `from`/`to` exactly equal its range
- `min`/`max` on date inputs is a UX hint only; server-side validation in `_parse_filters` remains the source of truth
- Keep Jinja autoescaping on for all echoed values; format dates for display with a Jinja filter or in Python, not by string slicing in the template
- Scope every query by `session["user_id"]`
- Existing tests and the `/profile/summary` JSON contract must keep passing unchanged

## Definition of done
- [ ] `/profile` shows a row of presets: This month, Last month, Last 7 days, Last 30 days, This year, All time
- [ ] Clicking "This month" loads `/profile?from=<1st of month>&to=<today>` and tiles, breakdown and list all reflect that range
- [ ] Clicking "Last month" shows the full previous calendar month (first to last day, inclusive), including when the current month is January
- [ ] "Last 7 days" and "Last 30 days" ranges end today and include the start date
- [ ] "All time" returns to unfiltered dates; a selected category is retained
- [ ] With `category=Food` selected, clicking any preset keeps `category=Food` in the URL and results
- [ ] The preset matching the current `from`/`to` is visually highlighted and has `aria-current="true"`; custom ranges highlight none
- [ ] From input has `max` = selected To date (when set) and To input has `min` = selected From date
- [ ] The active-filter line shows the date range in readable form, and the manual From/To/Category form still works with Apply and Clear
- [ ] `from` later than `to` still flashes an error and falls back to unfiltered; garbage values never cause a 500
- [ ] Presets with zero matching expenses show the existing "No expenses match these filters" empty state
- [ ] Works with JavaScript disabled
- [ ] Preset row and filter bar render correctly at ~375px and desktop widths (chips wrap, no horizontal scroll)
- [ ] No hardcoded hex values in new CSS
- [ ] `/profile/summary` still returns the same JSON shape and honours preset ranges
- [ ] `/`, `/login`, `/register`, `/terms`, `/privacy` still work and the app starts without errors
- [ ] `pytest` passes, including new tests for preset range calculation (month/year boundaries, leap-year February), category carry-over, active-preset detection and the rendered `min`/`max` attributes
