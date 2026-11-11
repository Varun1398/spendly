import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def test_get_login_shows_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b'name="email"' in resp.data
    assert b'name="password"' in resp.data


def test_valid_login_redirects_and_sets_session(client):
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    with client.session_transaction() as sess:
        assert sess["user_id"]
        assert sess["user_name"] == "Demo User"
    page = client.get("/profile")
    assert page.status_code == 200
    follow = client.get("/terms")
    assert b"Sign out" in follow.data


def test_email_case_and_whitespace_ignored(client):
    resp = login(client, email="  DEMO@Spendly.com ")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_wrong_password_rejected(client):
    resp = login(client, password="wrongpass")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_unknown_email_same_message(client):
    resp = login(client, email="nobody@example.com")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_failed_login_keeps_email_not_password(client):
    resp = login(client, email="demo@spendly.com", password="secretwrong")
    assert b'value="demo@spendly.com"' in resp.data
    assert b"secretwrong" not in resp.data


def test_register_then_login(client):
    client.post(
        "/register",
        data={"name": "Alice", "email": "alice@example.com", "password": "password123"},
    )
    resp = login(client, email="alice@example.com", password="password123")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_logout_clears_session_and_flashes(client):
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    follow = client.get("/login")
    assert b"signed out" in follow.data
    assert b"Get started" in follow.data
    assert b"Sign out" not in follow.data


def test_logout_when_not_logged_in(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_in_user_redirected_from_auth_pages(client, path):
    login(client)
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_session_holds_no_password_data(client):
    login(client)
    with client.session_transaction() as sess:
        assert set(sess.keys()) <= {"user_id", "user_name", "_flashes"}
        assert "demo123" not in str(dict(sess))
        assert "pbkdf2" not in str(dict(sess)) and "scrypt" not in str(dict(sess))


@pytest.mark.parametrize("path", ["/", "/register", "/terms", "/privacy"])
def test_other_pages_still_work(client, path):
    assert client.get(path).status_code == 200
