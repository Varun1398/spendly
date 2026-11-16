"""Tests for Step 7: Add Expense (spec: .claude/specs/07-add-expense.md)."""
from datetime import date, timedelta

import pytest

import database.db as db
from app import app as flask_app

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


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


def all_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
    finally:
        conn.close()


def expense_count():
    return len(all_expenses())


def user_id_for(email):
    return db.get_user_by_email(email)["id"]


def valid_form(**overrides):
    data = {
        "amount": "42.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Test dinner",
    }
    data.update(overrides)
    return data


def post_expense(client, **overrides):
    return client.post("/expenses/add", data=valid_form(**overrides))


# ---------- Auth guards ----------

def test_get_add_expense_logged_out_redirects_to_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_get_add_expense_logged_out_flashes_sign_in_message(client):
    resp = client.get("/expenses/add", follow_redirects=True)
    assert b"Please sign in to add an expense." in resp.data


def test_post_add_expense_logged_out_redirects_to_login(client):
    resp = post_expense(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_add_expense_logged_out_inserts_nothing(client):
    before = expense_count()
    post_expense(client)
    assert expense_count() == before


# ---------- GET form ----------

def test_get_add_expense_logged_in_returns_form(client):
    login(client)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.data.decode()
    for field in ("amount", "category", "date", "description"):
        assert f'name="{field}"' in body


def test_form_lists_all_seven_categories(client):
    login(client)
    body = client.get("/expenses/add").data.decode()
    for cat in CATEGORIES:
        assert cat in body


def test_form_date_defaults_to_today(client):
    login(client)
    body = client.get("/expenses/add").data.decode()
    assert date.today().isoformat() in body


def test_form_has_cancel_link_to_profile(client):
    login(client)
    body = client.get("/expenses/add").data.decode()
    assert 'href="/profile"' in body


# ---------- Happy path ----------

def test_valid_post_redirects_to_profile(client):
    login(client)
    resp = post_expense(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_valid_post_flashes_expense_added(client):
    login(client)
    resp = post_expense(client, description="Flash check")
    assert resp.status_code == 302
    page = client.get("/profile")
    assert b"Expense added." in page.data


def test_valid_post_follow_redirect_shows_flash_and_description(client):
    login(client)
    resp = client.post(
        "/expenses/add",
        data=valid_form(description="Unique sushi night"),
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Expense added." in resp.data
    assert b"Unique sushi night" in resp.data


def test_valid_post_inserts_row_with_submitted_values(client):
    login(client)
    before = expense_count()
    post_expense(client, amount="19.99", category="Transport", description="Taxi")
    rows = all_expenses()
    assert len(rows) == before + 1
    row = rows[-1]
    assert row["amount"] == pytest.approx(19.99)
    assert row["category"] == "Transport"
    assert row["date"] == date.today().isoformat()
    assert row["description"] == "Taxi"


def test_inserted_row_belongs_to_logged_in_user(client):
    login(client)
    post_expense(client)
    assert all_expenses()[-1]["user_id"] == user_id_for("demo@spendly.com")


def test_user_id_in_form_is_ignored(client):
    register_and_login(client)
    other_id = user_id_for("demo@spendly.com")
    post_expense(client, user_id=str(other_id))
    assert all_expenses()[-1]["user_id"] == user_id_for("alice@example.com")


def test_new_expense_not_visible_to_other_user(client):
    register_and_login(client)
    post_expense(client, description="Alice private purchase")
    client.get("/logout")
    login(client)
    body = client.get("/profile").data.decode()
    assert "Alice private purchase" not in body


def test_profile_total_updates_after_adding_expense(client):
    login(client)
    post_expense(client, amount="100.00", category="Bills", date=date.today().isoformat())
    body = client.get("/profile").data.decode()
    # seed total 400.24 + 100.00
    assert "₹500.24" in body


def test_new_user_can_add_first_expense_and_see_it(client):
    register_and_login(client)
    resp = client.post(
        "/expenses/add",
        data=valid_form(amount="7.25", description="First ever expense"),
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "First ever expense" in body
    assert "7.25" in body


def test_new_expense_appears_at_top_of_recent_expenses(client):
    register_and_login(client)
    post_expense(client, description="Older entry",
                 date=(date.today() - timedelta(days=5)).isoformat())
    post_expense(client, description="Newest entry", date=date.today().isoformat())
    body = client.get("/profile").data.decode()
    assert body.index("Newest entry") < body.index("Older entry")


def test_profile_has_add_expense_link(client):
    login(client)
    body = client.get("/profile").data.decode()
    assert "/expenses/add" in body


def test_empty_state_add_expense_link_present_for_new_user(client):
    register_and_login(client)
    body = client.get("/profile").data.decode()
    assert "/expenses/add" in body


@pytest.mark.parametrize("category", CATEGORIES)
def test_each_valid_category_is_accepted(client, category):
    login(client)
    before = expense_count()
    resp = post_expense(client, category=category)
    assert resp.status_code == 302
    assert expense_count() == before + 1


def test_amount_with_one_decimal_is_accepted(client):
    login(client)
    before = expense_count()
    post_expense(client, amount="5.5")
    assert expense_count() == before + 1


def test_integer_amount_is_accepted(client):
    login(client)
    before = expense_count()
    post_expense(client, amount="10")
    assert expense_count() == before + 1


def test_smallest_valid_amount_is_accepted(client):
    login(client)
    before = expense_count()
    post_expense(client, amount="0.01")
    assert expense_count() == before + 1


def test_upper_bound_amount_is_accepted(client):
    login(client)
    before = expense_count()
    post_expense(client, amount="10000000")
    assert expense_count() == before + 1


# ---------- Amount validation ----------

@pytest.mark.parametrize(
    "bad_amount",
    ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "nan", "NaN",
     "inf", "-inf", "Infinity", "1.234", "10.999", "10000000.01", "99999999999"],
)
def test_invalid_amount_rerenders_form_and_inserts_nothing(client, bad_amount):
    login(client)
    before = expense_count()
    resp = post_expense(client, amount=bad_amount)
    assert resp.status_code == 200
    assert b'name="amount"' in resp.data
    assert expense_count() == before


def test_missing_amount_field_inserts_nothing(client):
    login(client)
    before = expense_count()
    data = valid_form()
    del data["amount"]
    resp = client.post("/expenses/add", data=data)
    assert resp.status_code == 200
    assert expense_count() == before


def test_invalid_amount_shows_error_message(client):
    login(client)
    resp = post_expense(client, amount="-5")
    body = resp.data.decode().lower()
    assert "error" in body or "amount" in body


# ---------- Category validation ----------

@pytest.mark.parametrize("bad_category", ["", "Hacking", "food", "FOOD", "Food; DROP TABLE expenses", "  "])
def test_invalid_category_rerenders_form_and_inserts_nothing(client, bad_category):
    login(client)
    before = expense_count()
    resp = post_expense(client, category=bad_category)
    assert resp.status_code == 200
    assert expense_count() == before


def test_missing_category_field_inserts_nothing(client):
    login(client)
    before = expense_count()
    data = valid_form()
    del data["category"]
    resp = client.post("/expenses/add", data=data)
    assert resp.status_code == 200
    assert expense_count() == before


# ---------- Date validation ----------

@pytest.mark.parametrize(
    "bad_date",
    ["", "not-a-date", "2024-13-01", "2024-02-30", "01/02/2024", "2024/02/01", "20240201"],
)
def test_invalid_date_rerenders_form_and_inserts_nothing(client, bad_date):
    login(client)
    before = expense_count()
    resp = post_expense(client, date=bad_date)
    assert resp.status_code == 200
    assert expense_count() == before


def test_future_date_tomorrow_is_rejected(client):
    login(client)
    before = expense_count()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    resp = post_expense(client, date=tomorrow)
    assert resp.status_code == 200
    assert expense_count() == before


def test_far_future_date_is_rejected(client):
    login(client)
    before = expense_count()
    resp = post_expense(client, date="2999-01-01")
    assert resp.status_code == 200
    assert expense_count() == before


def test_today_date_is_accepted(client):
    login(client)
    before = expense_count()
    resp = post_expense(client, date=date.today().isoformat())
    assert resp.status_code == 302
    assert expense_count() == before + 1


def test_past_date_is_accepted(client):
    login(client)
    past = (date.today() - timedelta(days=400)).isoformat()
    resp = post_expense(client, date=past)
    assert resp.status_code == 302
    assert all_expenses()[-1]["date"] == past


# ---------- Description ----------

def test_empty_description_saved_as_null(client):
    login(client)
    post_expense(client, description="")
    assert all_expenses()[-1]["description"] is None


def test_whitespace_only_description_saved_as_null(client):
    login(client)
    post_expense(client, description="    ")
    assert all_expenses()[-1]["description"] is None


def test_missing_description_field_saved_as_null(client):
    login(client)
    data = valid_form()
    del data["description"]
    resp = client.post("/expenses/add", data=data)
    assert resp.status_code == 302
    assert all_expenses()[-1]["description"] is None


def test_description_is_stripped(client):
    login(client)
    post_expense(client, description="   padded text   ")
    assert all_expenses()[-1]["description"] == "padded text"


def test_description_of_exactly_200_chars_is_accepted(client):
    login(client)
    before = expense_count()
    resp = post_expense(client, description="x" * 200)
    assert resp.status_code == 302
    assert expense_count() == before + 1


def test_description_over_200_chars_is_rejected(client):
    login(client)
    before = expense_count()
    resp = post_expense(client, description="x" * 201)
    assert resp.status_code == 200
    assert expense_count() == before


# ---------- Re-fill values on error ----------

def test_error_rerender_keeps_entered_description(client):
    login(client)
    resp = post_expense(client, amount="-1", description="Keep this text")
    assert b"Keep this text" in resp.data


def test_error_rerender_keeps_entered_amount(client):
    login(client)
    resp = post_expense(client, amount="1.234")
    assert b"1.234" in resp.data


def test_error_rerender_keeps_entered_date(client):
    login(client)
    resp = post_expense(client, amount="abc", date="2023-05-17")
    assert b"2023-05-17" in resp.data


def test_error_rerender_keeps_selected_category(client):
    login(client)
    resp = post_expense(client, amount="abc", category="Health")
    body = resp.data.decode()
    # the Health option should be marked selected
    idx = body.index("Health")
    option_snippet = body[max(0, idx - 80): idx + 40]
    assert "selected" in option_snippet


# ---------- XSS / escaping ----------

def test_description_html_is_escaped_on_profile(client):
    login(client)
    post_expense(client, description="<script>alert(1)</script>")
    body = client.get("/profile").data.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_description_html_is_escaped_when_form_rerendered(client):
    login(client)
    resp = post_expense(client, amount="-1", description="<script>alert(1)</script>")
    body = resp.data.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


# ---------- SQL injection safety ----------

def test_sql_injection_in_description_is_stored_literally(client):
    login(client)
    payload = "x'); DROP TABLE expenses;--"
    post_expense(client, description=payload)
    rows = all_expenses()
    assert rows[-1]["description"] == payload


# ---------- Placeholders untouched ----------

def test_add_expense_endpoint_url_is_expenses_add():
    with flask_app.test_request_context():
        from flask import url_for
        assert url_for("add_expense") == "/expenses/add"
