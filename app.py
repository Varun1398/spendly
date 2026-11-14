import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_categories,
    get_category_totals,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


@app.template_filter("inr")
def inr(value):
    """Format a number as rupees with Indian digit grouping, e.g. ₹1,24,500.00."""
    whole, _, frac = f"{float(value or 0):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"₹{whole}.{frac}"


@app.template_filter("nicedate")
def nicedate(value):
    """Format YYYY-MM-DD as e.g. '1 Nov 2026'; return the input unchanged if invalid."""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return value
    return f"{d.day} {d.strftime('%b %Y')}"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


def _valid_email(email):
    local, _, domain = email.partition("@")
    return (
        bool(local)
        and "@" not in domain
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
        and " " not in email
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template("register.html", error=message, name=name, email=email)

    if not name:
        return fail("Name is required.")
    if not _valid_email(email):
        return fail("Enter a valid email address.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        return fail("An account with that email already exists.")

    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    flash(f"Welcome back, {user['name']}!", "success")
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


def _with_percentages(categories, grand_total):
    """Add an integer 'pct' to each category; percentages always sum to 100."""
    result = [dict(c, pct=0) for c in categories]
    if not result or grand_total <= 0:
        return result
    for c in result:
        c["pct"] = round(c["total"] / grand_total * 100)
    diff = 100 - sum(c["pct"] for c in result)
    max(result, key=lambda c: c["total"])["pct"] += diff
    return result


def _member_since(created_at):
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    except (TypeError, ValueError):
        return created_at or ""


def _parse_date(value):
    """Return value as canonical zero-padded YYYY-MM-DD if valid, else None."""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _parse_filters(args, user_id):
    """Validate ?from=&to=&category= and return (filters, error).

    `filters` keys match the db helper kwargs (date_from, date_to, category) so
    it can be passed as **filters. Invalid values are ignored. If from > to the
    filters are dropped entirely and an error message is returned.
    """
    filters = {
        "date_from": _parse_date(args.get("from", "").strip()),
        "date_to": _parse_date(args.get("to", "").strip()),
        "category": None,
    }
    category = args.get("category", "").strip()
    if category and category in get_categories(user_id):
        filters["category"] = category

    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        empty = {"date_from": None, "date_to": None, "category": None}
        return empty, "'From' date must not be after 'To' date. Showing all expenses."
    return filters, None


def _date_presets(today, filters):
    """Return quick date-range presets as [{key, label, args, active}, ...].

    `args` are the query params for url_for('profile', **args); the selected
    category is carried over, stale from/to are not. `active` is True when the
    current valid from/to exactly equal the preset's range.
    """
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - timedelta(days=1)
    ranges = [
        ("this_month", "This month", first_this_month, today),
        ("last_month", "Last month", last_prev_month.replace(day=1), last_prev_month),
        ("last_7", "Last 7 days", today - timedelta(days=6), today),
        ("last_30", "Last 30 days", today - timedelta(days=29), today),
        ("this_year", "This year", today.replace(month=1, day=1), today),
        ("all_time", "All time", None, None),
    ]
    current = (filters.get("date_from"), filters.get("date_to"))
    presets = []
    for key, label, start, end in ranges:
        dates = (start.isoformat(), end.isoformat()) if start else (None, None)
        args = {"from": dates[0], "to": dates[1]} if start else {}
        if filters.get("category"):
            args["category"] = filters["category"]
        presets.append({"key": key, "label": label, "args": args, "active": dates == current})
    return presets


# === SECTION 1: TRANSACTION HISTORY (Subagent 1) ===========================
# Owns: _transaction_history

def _transaction_history(user_id, filters):
    """Return the user's (filtered) expenses, newest first, as db rows."""
    return get_recent_expenses(
        user_id,
        limit=10,
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
        category=filters.get("category"),
    )

# === END SECTION 1 =========================================================


# === SECTION 2: SUMMARY STATS (Subagent 2) =================================
# Owns: _summary_stats and the GET /profile/summary JSON route

def _summary_stats(user_id, filters):
    """Return {'total': float, 'count': int, 'top_category': str | None}."""
    summary = get_expense_summary(user_id, **filters)
    categories = get_category_totals(user_id, **filters)
    return {
        "total": float(summary["total"]),
        "count": int(summary["count"]),
        "top_category": categories[0]["category"] if categories else None,
    }


@app.route("/profile/summary")
def profile_summary():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    filters, _error = _parse_filters(request.args, user_id)
    stats = _summary_stats(user_id, filters)
    return jsonify({
        "total": stats["total"],
        "count": stats["count"],
        "top_category": stats["top_category"],
        "categories": _category_breakdown(user_id, filters),
    })

# === END SECTION 2 =========================================================


# === SECTION 3: CATEGORY BREAKDOWN (Subagent 3) ============================
# Owns: _category_breakdown

def _category_breakdown(user_id, filters):
    """Return [{'category', 'total', 'pct'}, ...] highest first; pct sums to 100."""
    categories = get_category_totals(user_id, **filters)
    grand_total = sum(c["total"] for c in categories)
    return _with_percentages(categories, grand_total)

# === END SECTION 3 =========================================================


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please sign in to view your profile.", "error")
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    filters, error = _parse_filters(request.args, user_id)
    if error:
        flash(error, "error")

    stats = _summary_stats(user_id, filters)
    return render_template(
        "profile.html",
        user=user,
        summary={"total": stats["total"], "count": stats["count"]},
        top_category=stats["top_category"],
        categories=_category_breakdown(user_id, filters),
        expenses=_transaction_history(user_id, filters),
        member_since=_member_since(user["created_at"]),
        filters=filters,
        filtered=any(filters.values()),
        all_categories=get_categories(user_id),
        presets=_date_presets(date.today(), filters),
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
