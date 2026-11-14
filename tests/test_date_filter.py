"""Tests for Step 6: Date Filter for Profile Page (quick presets, min/max, labels).

Written from .claude/specs/06-date-filter-for-profile-page.md.
Data-driven tests use a fresh user with expenses dated relative to today so they
never depend on the demo seed data.
"""
import html
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

import database.db as db
from app import _date_presets, app as flask_app

ROOT = Path(__file__).resolve().parent.parent

PRESET_LABELS = [
    "This month",
    "Last month",
    "Last 7 days",
    "Last 30 days",
    "This year",
    "All time",
]


# ---------------------------------------------------------------- fixtures --

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def make_user(client, name, email):
    client.post(
        "/register",
        data={"name": name, "email": email, "password": "password123"},
    )
    return db.get_user_by_email(email)["id"]


def add_expense(user_id, when, description, amount=10.0, category="Food"):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, when.isoformat(), description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def alice(client):
    """A logged-in user with no expenses. Returns (client, user_id)."""
    uid = make_user(client, "Alice", "alice@example.com")
    login(client, "alice@example.com", "password123")
    return client, uid


# ----------------------------------------------------------------- helpers --

def presets_nav(body):
    match = re.search(r'<nav[^>]*class="prof-presets".*?</nav>', body, re.S)
    assert match, "preset row (nav.prof-presets) not found"
    return match.group(0)


def preset_links(body):
    """Return {label: {'href', 'tag', 'query'}} for every preset anchor."""
    links = {}
    for m in re.finditer(r"<a\s([^>]*)>\s*([^<]*?)\s*</a>", presets_nav(body)):
        attrs, label = m.group(1), m.group(2)
        href = re.search(r'href="([^"]*)"', attrs).group(1)
        href = html.unescape(href)
        links[label] = {
            "href": href,
            "tag": attrs,
            "query": parse_qs(urlparse(href).query),
        }
    return links


def get_links(client, query=""):
    body = client.get("/profile" + query).data.decode()
    return body, preset_links(body)


def input_tag(body, name):
    m = re.search(r'<input[^>]*name="%s"[^>]*>' % name, body)
    assert m, "input %s not found" % name
    return m.group(0)


def first_of_prev_month(today):
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


def last_of_prev_month(today):
    return today.replace(day=1) - timedelta(days=1)


def by_key(presets):
    return {p["key"]: p for p in presets}


# --------------------------------------------------- unit: _date_presets ----
# NOTE: the spec says _date_presets(today, category); the implementation takes
# (today, filters) where filters is the dict from _parse_filters. We follow the
# implemented signature but only assert on spec-described outputs.

def no_filters():
    return {"date_from": None, "date_to": None, "category": None}


def test_presets_list_has_six_in_spec_order():
    presets = _date_presets(date(2026, 11, 14), no_filters())
    assert [p["label"] for p in presets] == PRESET_LABELS


def test_this_month_runs_from_first_to_today():
    p = by_key(_date_presets(date(2026, 11, 14), no_filters()))["this_month"]
    assert p["args"]["from"] == "2026-11-01"
    assert p["args"]["to"] == "2026-11-14"


def test_last_month_in_january_is_previous_december():
    p = by_key(_date_presets(date(2026, 1, 15), no_filters()))["last_month"]
    assert p["args"]["from"] == "2025-12-01"
    assert p["args"]["to"] == "2025-12-31"


def test_last_month_after_leap_february_is_29_days():
    p = by_key(_date_presets(date(2024, 3, 10), no_filters()))["last_month"]
    assert p["args"]["from"] == "2024-02-01"
    assert p["args"]["to"] == "2024-02-29"


def test_last_month_after_non_leap_february_is_28_days():
    p = by_key(_date_presets(date(2025, 3, 10), no_filters()))["last_month"]
    assert p["args"]["from"] == "2025-02-01"
    assert p["args"]["to"] == "2025-02-28"


def test_last_month_from_the_31st_of_a_31_day_month():
    # May 31 -> April has 30 days
    p = by_key(_date_presets(date(2026, 5, 31), no_filters()))["last_month"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-04-01", "2026-04-30")


def test_last_month_on_march_31_is_february_not_an_error():
    p = by_key(_date_presets(date(2026, 3, 31), no_filters()))["last_month"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-02-01", "2026-02-28")


def test_last_month_on_july_31_is_30_day_june():
    p = by_key(_date_presets(date(2026, 7, 31), no_filters()))["last_month"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-06-01", "2026-06-30")


def test_last_month_when_previous_month_has_31_days():
    p = by_key(_date_presets(date(2026, 2, 28), no_filters()))["last_month"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-01-01", "2026-01-31")


def test_last_7_days_includes_start_date_and_ends_today():
    p = by_key(_date_presets(date(2026, 11, 14), no_filters()))["last_7"]
    # 7 days inclusive: 8..14 Nov
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-11-08", "2026-11-14")


def test_last_7_days_crosses_month_boundary():
    p = by_key(_date_presets(date(2026, 3, 3), no_filters()))["last_7"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-02-25", "2026-03-03")


def test_last_30_days_includes_start_date_and_ends_today():
    p = by_key(_date_presets(date(2026, 11, 30), no_filters()))["last_30"]
    # 30 days inclusive: 1..30 Nov
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-11-01", "2026-11-30")


def test_last_30_days_crosses_year_boundary():
    p = by_key(_date_presets(date(2026, 1, 10), no_filters()))["last_30"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2025-12-12", "2026-01-10")


def test_this_year_runs_from_jan_first_to_today():
    p = by_key(_date_presets(date(2026, 11, 14), no_filters()))["this_year"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2026-01-01", "2026-11-14")


def test_this_year_on_leap_day():
    p = by_key(_date_presets(date(2024, 2, 29), no_filters()))["this_year"]
    assert (p["args"]["from"], p["args"]["to"]) == ("2024-01-01", "2024-02-29")


def test_all_time_has_no_from_or_to():
    p = by_key(_date_presets(date(2026, 11, 14), no_filters()))["all_time"]
    assert "from" not in p["args"] and "to" not in p["args"]


def test_all_time_keeps_category_but_no_dates():
    filters = {"date_from": None, "date_to": None, "category": "Food"}
    p = by_key(_date_presets(date(2026, 11, 14), filters))["all_time"]
    assert p["args"] == {"category": "Food"}


def test_every_preset_carries_category_in_args():
    filters = {"date_from": None, "date_to": None, "category": "Food"}
    for p in _date_presets(date(2026, 11, 14), filters):
        assert p["args"].get("category") == "Food", p["key"]


def test_presets_do_not_carry_stale_from_to():
    filters = {"date_from": "2020-01-01", "date_to": "2020-02-01", "category": None}
    for p in _date_presets(date(2026, 11, 14), filters):
        assert p["args"].get("from") != "2020-01-01"
        assert p["args"].get("to") != "2020-02-01"


def test_preset_active_only_when_range_matches_exactly():
    today = date(2026, 11, 14)
    filters = {"date_from": "2026-11-01", "date_to": "2026-11-14", "category": None}
    active = [p["key"] for p in _date_presets(today, filters) if p["active"]]
    assert active == ["this_month"]


def test_preset_not_active_when_to_is_off_by_one_day():
    today = date(2026, 11, 14)
    filters = {"date_from": "2026-11-01", "date_to": "2026-11-13", "category": None}
    assert not any(p["active"] for p in _date_presets(today, filters))


def test_no_preset_active_for_custom_range():
    today = date(2026, 11, 14)
    filters = {"date_from": "2020-01-01", "date_to": "2020-01-31", "category": None}
    assert not any(p["active"] for p in _date_presets(today, filters))


# ------------------------------------------------------- auth guard ---------

def test_signed_out_profile_redirects_to_login(client):
    resp = client.get("/profile?from=2026-01-01&to=2026-01-31")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_signed_out_summary_returns_401(client):
    resp = client.get("/profile/summary?from=2026-01-01&to=2026-01-31")
    assert resp.status_code == 401


# ------------------------------------------------ rendering: preset row -----

def test_profile_shows_all_six_presets_in_order(alice):
    client, _ = alice
    body, links = get_links(client)
    assert list(links.keys()) == PRESET_LABELS


def test_presets_are_plain_links_to_profile(alice):
    client, _ = alice
    _, links = get_links(client)
    for label, link in links.items():
        assert urlparse(link["href"]).path == "/profile", label


def test_this_month_link_points_to_first_of_month_through_today(alice):
    client, _ = alice
    today = date.today()
    _, links = get_links(client)
    q = links["This month"]["query"]
    assert q["from"] == [today.replace(day=1).isoformat()]
    assert q["to"] == [today.isoformat()]


def test_last_month_link_covers_full_previous_month(alice):
    client, _ = alice
    today = date.today()
    _, links = get_links(client)
    q = links["Last month"]["query"]
    assert q["from"] == [first_of_prev_month(today).isoformat()]
    assert q["to"] == [last_of_prev_month(today).isoformat()]


def test_last_7_and_30_day_links_end_today(alice):
    client, _ = alice
    today = date.today()
    _, links = get_links(client)
    assert links["Last 7 days"]["query"]["from"] == [(today - timedelta(days=6)).isoformat()]
    assert links["Last 7 days"]["query"]["to"] == [today.isoformat()]
    assert links["Last 30 days"]["query"]["from"] == [(today - timedelta(days=29)).isoformat()]
    assert links["Last 30 days"]["query"]["to"] == [today.isoformat()]


def test_this_year_link_starts_jan_first(alice):
    client, _ = alice
    today = date.today()
    _, links = get_links(client)
    assert links["This year"]["query"]["from"] == [date(today.year, 1, 1).isoformat()]
    assert links["This year"]["query"]["to"] == [today.isoformat()]


def test_all_time_link_has_no_dates_when_no_category(alice):
    client, _ = alice
    _, links = get_links(client, "?from=2020-01-01&to=2020-02-01")
    assert links["All time"]["query"] == {}


# ------------------------------------------- category carry-over (HTTP) -----

def test_every_preset_link_keeps_selected_category(alice):
    client, uid = alice
    add_expense(uid, date.today(), "cat-carry", category="Food")
    _, links = get_links(client, "?category=Food")
    for label, link in links.items():
        assert link["query"].get("category") == ["Food"], label


def test_all_time_link_keeps_category_but_drops_dates(alice):
    client, uid = alice
    add_expense(uid, date.today(), "cat-carry", category="Food")
    _, links = get_links(client, "?category=Food&from=2020-01-01&to=2020-02-01")
    q = links["All time"]["query"]
    assert q == {"category": ["Food"]}


def test_preset_links_do_not_carry_stale_dates(alice):
    client, uid = alice
    add_expense(uid, date.today(), "cat-carry", category="Food")
    _, links = get_links(client, "?category=Food&from=2020-01-01&to=2020-02-01")
    for label, link in links.items():
        assert link["query"].get("from") != ["2020-01-01"], label
        assert link["query"].get("to") != ["2020-02-01"], label


def test_preset_links_have_no_category_when_none_selected(alice):
    client, _ = alice
    _, links = get_links(client)
    for label, link in links.items():
        assert "category" not in link["query"], label


def test_unknown_category_is_not_carried_over(alice):
    client, uid = alice
    add_expense(uid, date.today(), "cat-carry", category="Food")
    _, links = get_links(client, "?category=Nonexistent")
    for label, link in links.items():
        assert "category" not in link["query"], label


def test_category_with_special_characters_round_trips_in_preset_links(alice):
    client, uid = alice
    cat = "Eating Out & Drinks"
    add_expense(uid, date.today(), "special-cat", category=cat)
    _, links = get_links(client, "?" + "category=Eating%20Out%20%26%20Drinks")
    for label, link in links.items():
        assert link["query"].get("category") == [cat], label


# ------------------------------------------------ active preset detection ---

def active_labels(links):
    return [label for label, l in links.items() if 'aria-current="true"' in l["tag"]]


def test_only_all_time_active_on_unfiltered_profile(alice):
    # Spec: a preset is active when the valid from/to exactly equal its range;
    # "All time" (no from/to) therefore matches the unfiltered page.
    client, _ = alice
    _, links = get_links(client)
    assert active_labels(links) == ["All time"]


@pytest.mark.parametrize(
    "label",
    ["This month", "Last month", "Last 7 days", "Last 30 days", "This year"],
)
def test_visiting_a_preset_link_marks_it_active(alice, label):
    client, _ = alice
    _, links = get_links(client)
    href = links[label]["href"]
    _, links_after = get_links(client, href[len("/profile"):])
    assert label in active_labels(links_after)


def test_active_preset_has_active_css_class(alice):
    client, _ = alice
    _, links = get_links(client)
    href = links["Last month"]["href"]
    _, links_after = get_links(client, href[len("/profile"):])
    assert "is-active" in links_after["Last month"]["tag"]


def test_inactive_presets_have_no_aria_current(alice):
    client, _ = alice
    _, links = get_links(client)
    href = links["Last month"]["href"]
    _, links_after = get_links(client, href[len("/profile"):])
    for label, link in links_after.items():
        if label not in active_labels(links_after):
            assert "aria-current" not in link["tag"], label
            assert "is-active" not in link["tag"], label


def test_active_preset_stays_active_with_category_selected(alice):
    client, uid = alice
    add_expense(uid, date.today(), "cat-carry", category="Food")
    _, links = get_links(client)
    q = links["Last month"]["query"]
    suffix = "?from=%s&to=%s&category=Food" % (q["from"][0], q["to"][0])
    _, links_after = get_links(client, suffix)
    assert "Last month" in active_labels(links_after)


def test_custom_range_highlights_no_preset(alice):
    client, _ = alice
    _, links = get_links(client, "?from=2001-02-03&to=2001-02-10")
    assert active_labels(links) == []


def test_only_from_set_highlights_no_preset(alice):
    client, _ = alice
    first = date.today().replace(day=1).isoformat()
    _, links = get_links(client, "?from=" + first)
    assert active_labels(links) == []


def test_only_to_set_highlights_no_preset(alice):
    client, _ = alice
    _, links = get_links(client, "?to=" + date.today().isoformat())
    assert active_labels(links) == []


def test_range_off_by_one_day_highlights_no_preset(alice):
    client, _ = alice
    today = date.today()
    start = (today - timedelta(days=5)).isoformat()  # not a 7-day preset
    _, links = get_links(client, "?from=%s&to=%s" % (start, today.isoformat()))
    assert "Last 7 days" not in active_labels(links)


# ------------------------------------------- min / max on date inputs --------

def test_from_input_max_equals_selected_to_date(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-03-01&to=2026-03-31").data.decode()
    assert 'max="2026-03-31"' in input_tag(body, "from")


def test_to_input_min_equals_selected_from_date(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-03-01&to=2026-03-31").data.decode()
    assert 'min="2026-03-01"' in input_tag(body, "to")


def test_inputs_have_no_min_max_when_no_dates_selected(alice):
    client, _ = alice
    body = client.get("/profile").data.decode()
    assert "max=" not in input_tag(body, "from")
    assert "min=" not in input_tag(body, "to")


def test_only_from_selected_sets_to_min_but_no_from_max(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-03-01").data.decode()
    assert 'min="2026-03-01"' in input_tag(body, "to")
    assert "max=" not in input_tag(body, "from")


def test_only_to_selected_sets_from_max_but_no_to_min(alice):
    client, _ = alice
    body = client.get("/profile?to=2026-03-31").data.decode()
    assert 'max="2026-03-31"' in input_tag(body, "from")
    assert "min=" not in input_tag(body, "to")


def test_inputs_keep_selected_values(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-03-01&to=2026-03-31").data.decode()
    assert 'value="2026-03-01"' in input_tag(body, "from")
    assert 'value="2026-03-31"' in input_tag(body, "to")


def test_invalid_range_does_not_set_min_max(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-04-01&to=2026-03-01").data.decode()
    assert "max=" not in input_tag(body, "from")
    assert "min=" not in input_tag(body, "to")


# ----------------------------------------- readable active-filter label -----

def test_active_filter_line_shows_readable_date_range(alice):
    client, _ = alice
    body = client.get("/profile?from=2026-11-01&to=2026-11-14").data.decode()
    assert "1 Nov 2026" in body
    assert "14 Nov 2026" in body


def test_active_filter_line_shows_range_with_category(alice):
    client, uid = alice
    add_expense(uid, date(2026, 3, 5), "label-test", category="Food")
    body = client.get("/profile?from=2026-03-01&to=2026-03-31&category=Food").data.decode()
    assert "1 Mar 2026" in body
    assert "31 Mar 2026" in body
    assert "Food" in body


def test_manual_form_still_has_apply_and_clear(alice):
    client, _ = alice
    body = client.get("/profile").data.decode()
    assert "Apply" in body
    assert "Clear" in body
    assert 'name="category"' in body
    assert body.count('<form class="prof-filters"') == 1


# -------------------------------- results: presets filter data correctly ----

def follow(client, label, extra=""):
    _, links = get_links(client, extra)
    href = links[label]["href"]
    return client.get(href)


def test_this_month_preset_includes_first_and_today_excludes_before_and_after(alice):
    client, uid = alice
    today = date.today()
    first = today.replace(day=1)
    add_expense(uid, first, "zz-tm-first")
    add_expense(uid, today, "zz-tm-today")
    add_expense(uid, first - timedelta(days=1), "zz-tm-before")
    add_expense(uid, today + timedelta(days=1), "zz-tm-future")
    body = follow(client, "This month").data.decode()
    assert "zz-tm-first" in body
    assert "zz-tm-today" in body
    assert "zz-tm-before" not in body
    # tomorrow is outside "from 1st to today" (also true if it is next month)
    assert "zz-tm-future" not in body


def test_last_month_preset_includes_whole_previous_month_inclusive(alice):
    client, uid = alice
    today = date.today()
    first, last = first_of_prev_month(today), last_of_prev_month(today)
    add_expense(uid, first, "zz-lm-first")
    add_expense(uid, last, "zz-lm-last")
    add_expense(uid, first - timedelta(days=1), "zz-lm-before")
    add_expense(uid, today.replace(day=1), "zz-lm-after")
    body = follow(client, "Last month").data.decode()
    assert "zz-lm-first" in body
    assert "zz-lm-last" in body
    assert "zz-lm-before" not in body
    assert "zz-lm-after" not in body


def test_last_7_days_preset_includes_start_excludes_day_before(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today - timedelta(days=6), "zz-7-start")
    add_expense(uid, today, "zz-7-today")
    add_expense(uid, today - timedelta(days=7), "zz-7-out")
    body = follow(client, "Last 7 days").data.decode()
    assert "zz-7-start" in body
    assert "zz-7-today" in body
    assert "zz-7-out" not in body


def test_last_30_days_preset_includes_start_excludes_day_before(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today - timedelta(days=29), "zz-30-start")
    add_expense(uid, today - timedelta(days=30), "zz-30-out")
    body = follow(client, "Last 30 days").data.decode()
    assert "zz-30-start" in body
    assert "zz-30-out" not in body


def test_this_year_preset_includes_jan_first_excludes_previous_dec_31(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, date(today.year, 1, 1), "zz-ty-jan1")
    add_expense(uid, date(today.year - 1, 12, 31), "zz-ty-prev")
    body = follow(client, "This year").data.decode()
    assert "zz-ty-jan1" in body
    assert "zz-ty-prev" not in body


def test_all_time_preset_shows_expenses_from_any_date(alice):
    client, uid = alice
    add_expense(uid, date(2001, 5, 5), "zz-at-old")
    add_expense(uid, date.today(), "zz-at-new")
    # start from a narrow filter, then click All time
    body = follow(client, "All time", "?from=2020-01-01&to=2020-01-02").data.decode()
    assert "zz-at-old" in body
    assert "zz-at-new" in body


def test_all_time_with_category_filters_only_by_category(alice):
    client, uid = alice
    add_expense(uid, date(2001, 5, 5), "zz-food-old", category="Food")
    add_expense(uid, date(2001, 5, 6), "zz-bills-old", category="Bills")
    body = follow(client, "All time", "?category=Food").data.decode()
    assert "zz-food-old" in body
    assert "zz-bills-old" not in body


def test_preset_with_category_filters_results_by_category(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today, "zz-pc-food", category="Food")
    add_expense(uid, today, "zz-pc-bills", category="Bills")
    body = follow(client, "This month", "?category=Food").data.decode()
    assert "zz-pc-food" in body
    assert "zz-pc-bills" not in body


def test_preset_tiles_reflect_range(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today, "zz-tile-in", amount=100.0)
    add_expense(uid, today - timedelta(days=7), "zz-tile-out", amount=900.0)
    body = follow(client, "Last 7 days").data.decode()
    assert "₹100.00" in body
    assert "₹1,000.00" not in body


def test_preset_with_zero_matches_shows_empty_state(alice):
    client, _ = alice
    body = follow(client, "This month").data.decode()
    assert "No expenses match these filters" in body


def test_preset_does_not_show_other_users_expenses(client):
    alice_id = make_user(client, "Alice", "alice@example.com")
    bob_id = make_user(client, "Bob", "bob@example.com")
    add_expense(bob_id, date.today(), "zz-bob-secret", amount=777.0)
    add_expense(alice_id, date.today(), "zz-alice-own", amount=5.0)
    login(client, "alice@example.com", "password123")
    body = follow(client, "This month").data.decode()
    assert "zz-alice-own" in body
    assert "zz-bob-secret" not in body


# ------------------------------------------------ validation / no 500s ------

def test_from_after_to_flashes_error_and_shows_everything(alice):
    client, uid = alice
    add_expense(uid, date(2001, 1, 1), "zz-bad-range")
    resp = client.get("/profile?from=2026-04-01&to=2026-03-01")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "must not be after" in body
    assert "zz-bad-range" in body


def test_from_after_to_highlights_no_dated_preset(alice):
    # Falls back to unfiltered, so only "All time" may be highlighted.
    client, _ = alice
    _, links = get_links(client, "?from=2026-04-01&to=2026-03-01")
    assert active_labels(links) in ([], ["All time"])


@pytest.mark.parametrize(
    "query",
    [
        "?from=garbage",
        "?to=garbage",
        "?from=garbage&to=garbage",
        "?from=2026-02-30&to=2026-02-31",
        "?from=2026-13-01",
        "?from=26-1-1",
        "?from=&to=",
        "?from=2026-11-01&to=",
        "?from=%3Cscript%3Ealert(1)%3C/script%3E",
        "?category=%27%20OR%201%3D1%20--",
        "?category=" + "A" * 5000,
        "?from=" + "9" * 5000,
        "?from=2026-11-01&from=2026-11-02&to=2026-11-05&to=bad",
        "?from=0000-00-00",
        "?from=9999-12-31&to=9999-12-31",
        "?from=%00&to=%00",
    ],
)
def test_garbage_query_values_never_cause_500(alice, query):
    client, _ = alice
    resp = client.get("/profile" + query)
    assert resp.status_code == 200
    resp = client.get("/profile/summary" + query)
    assert resp.status_code == 200


def test_garbage_dates_are_ignored_and_show_unfiltered_results(alice):
    client, uid = alice
    add_expense(uid, date(2001, 1, 1), "zz-garbage-ok")
    body = client.get("/profile?from=garbage&to=nonsense").data.decode()
    assert "zz-garbage-ok" in body


def test_leap_day_is_accepted_as_a_valid_date(alice):
    client, uid = alice
    add_expense(uid, date(2024, 2, 29), "zz-leap-day")
    body = client.get("/profile?from=2024-02-29&to=2024-02-29").data.decode()
    assert "zz-leap-day" in body


def test_feb_29_in_non_leap_year_is_ignored_not_500(alice):
    client, uid = alice
    add_expense(uid, date(2001, 1, 1), "zz-nonleap")
    resp = client.get("/profile?from=2025-02-29&to=2025-02-29")
    assert resp.status_code == 200
    assert "zz-nonleap" in resp.data.decode()


def test_echoed_category_is_html_escaped(alice):
    client, _ = alice
    body = client.get("/profile?category=%3Cscript%3Ealert(1)%3C/script%3E").data.decode()
    assert "<script>alert(1)</script>" not in body


# --------------------------------------------------- /profile/summary -------

def test_summary_json_shape_is_unchanged(alice):
    client, uid = alice
    add_expense(uid, date.today(), "zz-shape", amount=20.0, category="Food")
    data = client.get("/profile/summary").get_json()
    assert set(data.keys()) == {"total", "count", "top_category", "categories"}
    assert set(data["categories"][0].keys()) == {"category", "total", "pct"}


def test_summary_honours_last_7_days_preset_range(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today, "in-range", amount=40.0)
    add_expense(uid, today - timedelta(days=6), "in-range-start", amount=60.0)
    add_expense(uid, today - timedelta(days=7), "out-of-range", amount=500.0)
    _, links = get_links(client)
    q = links["Last 7 days"]["query"]
    data = client.get(
        "/profile/summary?from=%s&to=%s" % (q["from"][0], q["to"][0])
    ).get_json()
    assert data["count"] == 2
    assert data["total"] == pytest.approx(100.0)


def test_summary_honours_last_month_preset_range(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, first_of_prev_month(today), "lm-a", amount=10.0)
    add_expense(uid, last_of_prev_month(today), "lm-b", amount=20.0)
    add_expense(uid, today.replace(day=1), "this-month", amount=300.0)
    _, links = get_links(client)
    q = links["Last month"]["query"]
    data = client.get(
        "/profile/summary?from=%s&to=%s" % (q["from"][0], q["to"][0])
    ).get_json()
    assert data["count"] == 2
    assert data["total"] == pytest.approx(30.0)


def test_summary_with_preset_range_and_category(alice):
    client, uid = alice
    today = date.today()
    add_expense(uid, today, "food", amount=10.0, category="Food")
    add_expense(uid, today, "bills", amount=90.0, category="Bills")
    data = client.get(
        "/profile/summary?from=%s&to=%s&category=Food"
        % (today.replace(day=1).isoformat(), today.isoformat())
    ).get_json()
    assert data["count"] == 1
    assert data["top_category"] == "Food"


def test_summary_with_empty_preset_range_returns_zeroes(alice):
    client, _ = alice
    data = client.get("/profile/summary?from=2000-01-01&to=2000-01-31").get_json()
    assert data["total"] == 0
    assert data["count"] == 0
    assert data["top_category"] is None
    assert data["categories"] == []


# --------------------------------------------------- CSS / other pages ------

def test_preset_css_exists_with_active_state():
    css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    assert ".prof-preset" in css
    assert ".prof-preset.is-active" in css


def test_preset_css_has_no_hardcoded_hex_values():
    css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    blocks = re.findall(r"[^{}]*\.prof-preset[^{}]*\{[^{}]*\}", css)
    assert blocks, "no preset rules found"
    for block in blocks:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block), block


def test_preset_css_uses_css_variables():
    css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
    blocks = re.findall(r"[^{}]*\.prof-preset[^{}]*\{[^{}]*\}", css)
    assert any("var(--" in b for b in blocks)


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/terms", "/privacy"])
def test_public_pages_still_work(client, path):
    assert client.get(path).status_code == 200


def test_demo_user_profile_still_renders_with_presets(client):
    login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert list(preset_links(resp.data.decode()).keys()) == PRESET_LABELS
