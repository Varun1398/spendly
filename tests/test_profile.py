import pytest

import database.db as db
from app import _with_percentages, app as flask_app, inr


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def register_and_login(client, name="Alice", email="alice@example.com"):
    client.post(
        "/register",
        data={"name": name, "email": email, "password": "password123"},
    )
    return login(client, email=email, password="password123")


def test_signed_out_redirects_to_login_with_message(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    page = client.get("/login")
    assert b"Please sign in to view your profile." in page.data


def test_demo_user_profile_content(client):
    login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "Member since" in body
    assert "₹400.24" in body
    assert "Bills" in body
    for desc in (
        "Lunch at cafe",
        "Monthly metro pass top-up",
        "Electricity bill",
        "Pharmacy",
        "Movie tickets",
        "New shoes",
        "Miscellaneous",
        "Groceries",
    ):
        assert desc in body


def test_recent_expenses_newest_first(client):
    login(client)
    body = client.get("/profile").data.decode()
    assert body.index("Groceries") < body.index("Lunch at cafe")


def test_categories_sorted_highest_first(client):
    login(client)
    body = client.get("/profile").data.decode()
    assert body.index("Bills") < body.index("Shopping") < body.index("Transport")


def test_percentages_sum_to_100():
    cats = [
        {"category": "A", "total": 1.0},
        {"category": "B", "total": 1.0},
        {"category": "C", "total": 1.0},
    ]
    result = _with_percentages(cats, 3.0)
    assert sum(c["pct"] for c in result) == 100


def test_percentages_handle_empty_and_zero():
    assert _with_percentages([], 0) == []
    zero = _with_percentages([{"category": "A", "total": 0}], 0)
    assert zero[0]["pct"] == 0


def test_inr_filter_indian_grouping():
    assert inr(400.24) == "₹400.24"
    assert inr(124500) == "₹1,24,500.00"
    assert inr(0) == "₹0.00"
    assert inr(1234567.5) == "₹12,34,567.50"


def test_new_user_sees_empty_state(client):
    register_and_login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "₹0.00" in body
    assert "No expenses yet" in body
    assert "Alice" in body


def test_users_only_see_their_own_expenses(client):
    register_and_login(client)
    conn = db.get_db()
    try:
        alice_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("alice@example.com",)
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (alice_id, 777.0, "Travel", "2026-01-01", "Alice secret trip"),
        )
        conn.commit()
    finally:
        conn.close()

    alice_page = client.get("/profile").data.decode()
    assert "Alice secret trip" in alice_page
    assert "Electricity bill" not in alice_page

    client.get("/logout")
    login(client)
    demo_page = client.get("/profile").data.decode()
    assert "Alice secret trip" not in demo_page
    assert "Electricity bill" in demo_page


def test_stale_session_redirects_and_clears(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
        sess["user_name"] = "Ghost"
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_user_name_is_escaped(client):
    register_and_login(client, name="<script>alert(1)</script>", email="x@example.com")
    body = client.get("/profile").data.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_navbar_name_links_to_profile(client):
    login(client)
    body = client.get("/terms").data.decode()
    assert 'href="/profile" class="nav-user"' in body


def test_profile_css_has_no_hex_colors():
    import re
    from pathlib import Path

    css = (Path(__file__).resolve().parent.parent / "static/css/profile.css").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


# ------------------------------------------------------------------ #
# Step 5 — filters and /profile/summary                               #
# ------------------------------------------------------------------ #

def _expense_dates(client):
    """Return {description: iso date} for the demo user's seeded expenses."""
    conn = db.get_db()
    try:
        rows = conn.execute("SELECT description, date FROM expenses").fetchall()
    finally:
        conn.close()
    return {r["description"]: r["date"] for r in rows}


def test_no_filters_unchanged(client):
    login(client)
    body = client.get("/profile").data.decode()
    assert "₹400.24" in body
    assert "Groceries" in body and "Electricity bill" in body


def test_category_filter(client):
    login(client)
    body = client.get("/profile?category=Food").data.decode()
    assert "Lunch at cafe" in body and "Groceries" in body
    assert "Electricity bill" not in body
    assert "₹45.25" in body  # 12.50 + 32.75


def test_date_bounds_are_inclusive_and_independent(client):
    login(client)
    d = _expense_dates(client)
    day = d["Electricity bill"]
    both = client.get(f"/profile?from={day}&to={day}").data.decode()
    assert "Electricity bill" in both and "Pharmacy" not in both
    only_from = client.get(f"/profile?from={day}").data.decode()
    assert "Electricity bill" in only_from and "Lunch at cafe" not in only_from
    only_to = client.get(f"/profile?to={day}").data.decode()
    assert "Electricity bill" in only_to and "Pharmacy" not in only_to


def test_no_match_shows_empty_state(client):
    login(client)
    resp = client.get("/profile?from=2000-01-01&to=2000-01-31")
    assert resp.status_code == 200
    assert "No expenses match these filters" in resp.data.decode()


def test_from_after_to_flashes_and_falls_back(client):
    login(client)
    resp = client.get("/profile?from=2026-12-01&to=2026-01-01", follow_redirects=True)
    body = resp.data.decode()
    assert "must not be after" in body
    assert "₹400.24" in body


def test_garbage_filters_do_not_error(client):
    login(client)
    for qs in ("from=abc", "to=99-99-99", "category=Nope", "category=<script>alert(1)</script>"):
        resp = client.get("/profile?" + qs)
        assert resp.status_code == 200
        assert "<script>alert(1)</script>" not in resp.data.decode()


def test_filter_bar_prefilled(client):
    login(client)
    body = client.get("/profile?category=Bills&from=2020-01-01").data.decode()
    assert 'value="2020-01-01"' in body
    assert 'value="Bills" selected' in body


def test_summary_requires_login(client):
    resp = client.get("/profile/summary")
    assert resp.status_code == 401
    assert resp.is_json


def test_summary_json_shape_and_totals(client):
    login(client)
    data = client.get("/profile/summary").get_json()
    assert data["count"] == 8
    assert round(data["total"], 2) == 400.24
    assert data["top_category"] == "Bills"
    assert sum(c["pct"] for c in data["categories"]) == 100
    assert "password_hash" not in str(data)


def test_summary_honours_filters(client):
    login(client)
    data = client.get("/profile/summary?category=Food").get_json()
    assert data["count"] == 2
    assert round(data["total"], 2) == 45.25
    assert [c["category"] for c in data["categories"]] == ["Food"]


def test_filters_and_summary_are_isolated_per_user(client):
    register_and_login(client)
    data = client.get("/profile/summary?category=Food").get_json()
    assert data["count"] == 0 and data["total"] == 0
    assert data["categories"] == []
    assert "Lunch at cafe" not in client.get("/profile?category=Food").data.decode()
