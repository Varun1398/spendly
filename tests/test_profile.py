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
