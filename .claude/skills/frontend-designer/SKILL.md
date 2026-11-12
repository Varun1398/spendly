---
name: spendly-ui
description: Design and build modern, production-ready UI pages and components for Spendly, the friendly Flask expense tracker — Jinja templates, plain CSS on Spendly's design tokens, and vanilla JS. Use this whenever the user asks to create, design, style, redesign or polish any Spendly screen or piece of UI (dashboard, profile, add/edit/delete expense, expense list, filters, charts, empty states, forms, modals, navbar, flash messages), even if they only say "make the page", "build the UI for step N", "make it look nicer" or name a template or CSS file in this repo.
---

# Spendly UI Designer

Spendly is a calm, friendly expense tracker. Its look is warm and editorial: off-white "paper" backgrounds, a deep forest-green accent, a serif display face for headings and amounts, and plenty of whitespace. Every new screen should feel like it came from the same hand as the existing landing and auth pages. A user should never be able to tell which page was built last.

The stack is deliberately simple: **Flask + Jinja templates + plain CSS + vanilla JS, no build step, no new dependencies.** Don't add Tailwind, Bootstrap, React, chart libraries or icon packs. The project is a teaching codebase, and every extra dependency is one more thing a learner has to understand. Everything below can be done with the platform.

## Before you write anything

Read these files first. They change as the project grows, so don't rely on memory:

1. `CLAUDE.md` for the architecture and which routes are still stubs.
2. The relevant spec in `.claude/specs/` if one exists for this step. Its "Rules for implementation" and "Definition of done" override anything here.
3. `templates/base.html` for the blocks available (`title`, `head`, `content`, `scripts`), the navbar and the flash messages.
4. `static/css/style.css` for the tokens in `:root` and the classes that already exist (`.btn-primary`, `.btn-ghost`, `.form-group`, `.form-input`, `.btn-submit`, `.auth-card`, `.auth-error`, `.auth-success`). Reuse before you reinvent.
5. `database/db.py` for the real column names (`expenses`: `id, user_id, amount, category, date, description, created_at`).

Then read `references/components.md` for the ready-made patterns (page header, stat cards, expense list, category chips, forms, empty states, delete confirmation, CSS-only charts) and adapt them instead of starting from scratch.

## Design language

**Color.** Use only the CSS variables in `:root`, and never write a hex value in a page stylesheet or template. If a design genuinely needs a new color (for example, more category colors), add a named token to `:root` in `style.css` and use that. Note that `landing.css` hardcodes some greens; don't copy from it. The roles:

- `--paper` is the page background, `--paper-warm` is for banded sections, and `--paper-card` is for cards.
- `--ink` is for primary text and primary buttons. `--ink-soft`, `--ink-muted` and `--ink-faint` step down through labels, secondary text and placeholders.
- `--accent` (forest green) is the brand color: links, focus, positive states and the main data series. `--accent-light` is its tinted background.
- `--accent-2` (amber) is a secondary highlight. Use it sparingly, for example a "this month" badge or the second data series.
- `--danger` and `--danger-light` are only for destructive actions and errors.
- `--border` and `--border-soft` are for 1px hairlines. Spendly separates things with hairlines and space, not heavy shadows.

**Type.** `--font-display` (DM Serif Display) is for page titles, card titles and big money figures. `--font-body` (DM Sans) is for everything else. Use weights 400, 500 and 600 only. Small uppercase labels use about `0.75–0.8rem`, weight 500, `letter-spacing: 0.06em`, in `--ink-muted` (see `.mock-label`).

**Shape and depth.** The radii are `--radius-sm` (inputs, buttons), `--radius-md` (cards) and `--radius-lg` (hero or feature panels). Cards are `--paper-card` with a `1px solid var(--border)` border. If you use a shadow at all, keep it very soft: `0 8px 40px rgba(0,0,0,0.06)`.

**Space and layout.** Content is centred in `max-width: var(--max-width)` with `2rem` side padding (`1rem` under 600px). Use rem units on a roughly 0.25rem rhythm. Use CSS grid for page layout and flex for rows. The existing breakpoints are `900px` (two columns become one) and `600px` (phones). Use those, not new ones.

**Money.** Amounts are rupees. Show them with the `₹` symbol and Indian digit grouping (₹1,24,500.00), and set totals in `--font-display`. Use `font-variant-numeric: tabular-nums` wherever numbers line up in a column. Format on the server: if the app doesn't yet have an `inr` Jinja filter, add the one from `references/components.md` to `app.py`. That keeps every template consistent.

**Voice.** Spendly is friendly but not cute. Copy is short, warm and plain: "No expenses yet. Add your first one to see where your money goes." is better than both "No data" and "Oops! 🙈". Buttons say what they do ("Add expense", "Save changes", "Delete expense"). The footer tagline sets the tone: *Track every rupee. Own your finances.*

## How to build a page

1. **Template.** Create or modify `templates/<page>.html` and make it `{% extends "base.html" %}`. Fill `title` as "Page name — Spendly". Use `url_for(...)` for every link and form action. Don't use inline `style=""` attributes.
2. **CSS.** Put page-specific styles in `static/css/<page>.css` and load it in `{% block head %}`. This mirrors `landing.css`. Put genuinely shared components (cards, buttons, chips, the stat grid) in `style.css` under a clearly commented section that matches the file's existing `/* --- */` banner style, so the next page can reuse them. Prefix page classes to avoid collisions (e.g. `.dash-`, `.exp-`).
3. **JS (only if it earns its place).** Pages must work fully without JavaScript: forms POST to Flask, and links navigate. JS is progressive enhancement only, such as auto-dismissing flash messages, live-filtering a list, a delete-confirm dialog, or keeping the amount input tidy. Put page-specific JS in `static/js/<page>.js` and load it in `{% block scripts %}`. Wrap it in a check that the elements exist.
4. **Route.** If the page needs a route, replace the stub in `app.py`. Don't add a duplicate. Protect logged-in pages (redirect to `url_for('login')` when `session.get("user_id")` is missing) and only query the current user's rows with parameterised SQL. Keep data access in `database/db.py` helpers, not inline in the route.
5. **States.** Design every state, not just the happy path:
   - **Empty:** first-time user, or no results after a filter. Explain and offer the next action.
   - **Error:** the form re-renders with the message in `.auth-error` style and keeps the user's input (never the password).
   - **Success:** flash a message and redirect (POST/redirect/GET).
   - **Long content:** long descriptions truncate with an ellipsis, and many rows still read well.

## Production-ready checklist

Before you call it done, check each of these. They're what separate a real product from a demo:

- **Accessible.** Every input has a `<label for>`. Icon-only buttons have `aria-label`. Use semantic elements (`<main>`, `<section>`, `<table>` for tabular data, `<button>` for actions, `<a>` for navigation). Add a visible `:focus-visible` outline using `--accent`. Color is never the only signal (pair red with text or an icon). Text contrast should be at least `--ink-muted` on `--paper`. Respect `prefers-reduced-motion` for any animation.
- **Responsive.** Check it mentally at 375px, 768px and 1200px. Make sure there's no horizontal scroll, that tables collapse to stacked cards under 600px, and that tap targets are at least 44px.
- **Safe.** Destructive actions (delete) go through a POST form with a confirmation step, never a bare GET link. Let Jinja autoescape user text; don't use `|safe` on user data. Inputs carry sensible constraints (`type="number" step="0.01" min="0.01"`, `type="date"`, `required`, `maxlength`), and the server validates the same rules again.
- **Consistent.** It uses tokens only and reuses existing button and form classes. Headings use the display font. It sits visually beside `login.html` and `landing.html` without clashing.
- **Not broken.** Run `pytest` if tests exist for this area, and run `python app.py` to render the page once if you can. Fix any Jinja errors before finishing.

## Output

Tell the user which files you created or changed, show any new routes or `db.py` helpers, and mention design decisions they might want to revisit (for example, "I added 4 category color tokens to `:root`"). Keep the summary short. The code is the deliverable.