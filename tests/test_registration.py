import pytest
from werkzeug.security import check_password_hash

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def user_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def register(client, name="Alice", email="alice@example.com", password="password123"):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password}
    )


def test_get_register_shows_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    for field in (b'name="name"', b'name="email"', b'name="password"'):
        assert field in resp.data


def test_valid_registration_creates_hashed_user_and_redirects(client):
    before = user_count()
    resp = register(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert user_count() == before + 1

    user = db.get_user_by_email("alice@example.com")
    assert user["name"] == "Alice"
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")

    page = client.get("/login")
    assert b"Account created" in page.data


def test_success_message_shown_after_redirect(client):
    resp = register(client)
    follow = client.get(resp.headers["Location"])
    assert b"Account created" in follow.data


@pytest.mark.parametrize("email", ["demo@spendly.com", "DEMO@Spendly.com"])
def test_duplicate_email_rejected(client, email):
    before = user_count()
    resp = register(client, email=email)
    assert resp.status_code == 200
    assert b"already exists" in resp.data
    assert user_count() == before


def test_short_password_rejected(client):
    before = user_count()
    resp = register(client, password="1234567")
    assert b"at least 8 characters" in resp.data
    assert user_count() == before


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_name_rejected(client, name):
    before = user_count()
    resp = register(client, name=name)
    assert b"Name is required" in resp.data
    assert user_count() == before


@pytest.mark.parametrize("email", ["", "foo", "a@b", "@example.com", "a b@example.com"])
def test_invalid_email_rejected(client, email):
    before = user_count()
    resp = register(client, email=email)
    assert b"valid email" in resp.data
    assert user_count() == before


def test_form_keeps_name_and_email_but_not_password(client):
    resp = register(client, name="Bob", email="bob@example.com", password="short")
    assert b'value="Bob"' in resp.data
    assert b'value="bob@example.com"' in resp.data
    assert b"short" not in resp.data.replace(b"Password must be at least", b"")


@pytest.mark.parametrize("path", ["/", "/login", "/terms", "/privacy"])
def test_other_pages_still_work(client, path):
    assert client.get(path).status_code == 200
