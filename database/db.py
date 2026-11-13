import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "spendly.db")


def get_db():
    """Return a SQLite connection with dict-like rows and foreign keys enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to call repeatedly."""
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    """Return the user row for this email, or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return id, name, email, created_at for this user (no password hash), or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()


def _expense_filter(user_id, date_from=None, date_to=None, category=None):
    """Build a WHERE clause from fixed fragments; values are always bound params."""
    clauses, params = ["user_id = ?"], [user_id]
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    if category:
        clauses.append("category = ?")
        params.append(category)
    return " AND ".join(clauses), params


def get_categories(user_id):
    """Return this user's distinct expense categories, sorted."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM expenses WHERE user_id = ? ORDER BY category",
            (user_id,),
        ).fetchall()
        return [r["category"] for r in rows]
    finally:
        conn.close()


def get_expense_summary(user_id, date_from=None, date_to=None, category=None):
    """Return {'total': float, 'count': int} for this user's (filtered) expenses."""
    where, params = _expense_filter(user_id, date_from, date_to, category)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE " + where,
            params,
        ).fetchone()
        return {"total": row["total"], "count": row["count"]}
    finally:
        conn.close()


def get_category_totals(user_id, date_from=None, date_to=None, category=None):
    """Return [{'category', 'total'}, ...] for this user, highest total first."""
    where, params = _expense_filter(user_id, date_from, date_to, category)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE " + where +
            " GROUP BY category ORDER BY total DESC, category",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None, category=None):
    """Return this user's (filtered) expenses, newest first."""
    where, params = _expense_filter(user_id, date_from, date_to, category)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses WHERE "
            + where + " ORDER BY date DESC, id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    finally:
        conn.close()


def create_user(name, email, password):
    """Insert a user with a hashed password and return the new id.

    Raises sqlite3.IntegrityError if the email already exists.
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def seed_db():
    """Insert a demo user and sample expenses once; no-op if users exist."""
    conn = get_db()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return

        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cur.lastrowid

        today = date.today()
        samples = [
            (1, 12.50, "Food", "Lunch at cafe"),
            (3, 45.00, "Transport", "Monthly metro pass top-up"),
            (5, 120.00, "Bills", "Electricity bill"),
            (8, 60.00, "Health", "Pharmacy"),
            (11, 25.00, "Entertainment", "Movie tickets"),
            (14, 89.99, "Shopping", "New shoes"),
            (18, 15.00, "Other", "Miscellaneous"),
            (22, 32.75, "Food", "Groceries"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, amount, category, today.replace(day=day).isoformat(), desc)
                for day, amount, category, desc in samples
            ],
        )
        conn.commit()
    finally:
        conn.close()
