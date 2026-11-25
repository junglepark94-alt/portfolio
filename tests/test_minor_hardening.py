import io
import urllib.error

import pytest

import app as app_module
from app import DailyVisit, GalleryItem, Project, VisitEvent, db


@pytest.fixture(autouse=True)
def clean_rate_limits():
    app_module._RATE_HITS.clear()
    yield
    app_module._RATE_HITS.clear()


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


# ── 로그아웃은 POST + CSRF ──────────────────────────────

def test_logout_rejects_get(client):
    _login(client)
    assert client.get("/admin/logout").status_code == 405
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


def test_logout_post_clears_login(client):
    _login(client)
    resp = client.post("/admin/logout")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "logged_in" not in sess


def test_logout_post_requires_csrf_token(client, portfolio_app, monkeypatch):
    _login(client)
    monkeypatch.setitem(portfolio_app.config, "WTF_CSRF_ENABLED", True)
    assert client.post("/admin/logout").status_code == 400
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


def test_admin_dashboard_renders_logout_as_post_form(client):
    _login(client)
    html = client.get("/admin").get_data(as_text=True)
    assert 'method="post" action="/admin/logout"' in html


# ── 재정렬 API 입력 검증 ────────────────────────────────

@pytest.mark.parametrize("payload", [
    {"ids": ["abc"]},
    {"ids": [None]},
    {"ids": [True]},
    {"ids": "1,2"},
    ["1", "2"],
    None,
])
def test_reorder_rejects_malformed_ids_without_changes(client, portfolio_app, payload):
    _login(client)
    with portfolio_app.app_context():
        before = [(p.id, p.order) for p in Project.query.all()]
    kwargs = {"json": payload} if payload is not None else {"data": "not json"}
    for url in ("/admin/projects/reorder", "/admin/gallery/reorder"):
        assert client.post(url, **kwargs).status_code == 400
    with portfolio_app.app_context():
        assert [(p.id, p.order) for p in Project.query.all()] == before


def test_reorder_accepts_numeric_strings(client, portfolio_app):
    _login(client)
    with portfolio_app.app_context():
        pid = Project.query.first().id
        gid = GalleryItem.query.first().id
    assert client.post("/admin/projects/reorder", json={"ids": [str(pid)]}).status_code == 200
    assert client.post("/admin/gallery/reorder", json={"ids": [gid]}).status_code == 200
    with portfolio_app.app_context():
        assert db.session.get(Project, pid).order == 0
        assert db.session.get(GalleryItem, gid).sort_order == 0


# ── 이미지 다운로드 리다이렉트 제한 ───────────────────────

def _redirect(newurl):
    handler = app_module._AllowedHostRedirectHandler()
    req = urllib.request.Request("https://img.youtube.com/vi/abcdefghijk/maxresdefault.jpg")
    return handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, newurl)


def test_image_redirect_to_allowed_host_is_followed():
    assert _redirect("https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg").full_url.startswith("https://i.ytimg.com/")


@pytest.mark.parametrize("newurl", [
    "https://evil.example.com/a.jpg",
    "http://i.ytimg.com/a.jpg",
    "http://169.254.169.254/latest/meta-data",
])
def test_image_redirect_to_other_host_is_blocked(newurl):
    with pytest.raises(urllib.error.HTTPError):
        _redirect(newurl)


def test_download_returns_none_when_redirect_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))

    def blocked(url, timeout):
        raise urllib.error.HTTPError(url, 302, "redirect to disallowed host", {}, None)

    monkeypatch.setattr(app_module, "_open_image_url", blocked)
    assert app_module._download_image("https://img.youtube.com/vi/x/hqdefault.jpg", "yt_x.jpg") is None
    assert not (tmp_path / "yt_x.jpg").exists()


# ── 같은 세션의 재방문은 DB를 건드리지 않는다 ──────────────

def test_repeat_visit_skips_database_work(client, portfolio_app, monkeypatch):
    calls = []
    real_record = app_module.record_event
    monkeypatch.setattr(app_module, "record_event", lambda *a, **k: calls.append("record") or real_record(*a, **k))
    monkeypatch.setattr(app_module, "prune_visit_events", lambda *a, **k: calls.append("prune") or 0)

    for _ in range(3):
        assert client.get("/").status_code == 200
    assert calls == ["prune", "record"]
    with portfolio_app.app_context():
        assert VisitEvent.query.filter_by(stage="visit").count() == 1
        assert DailyVisit.query.one().count == 1


def test_legacy_session_key_is_migrated_without_double_counting(client, portfolio_app):
    today = app_module._today_kst()
    with client.session_transaction() as sess:
        sess[f"v_{today}"] = True          # 예전 코드가 이미 오늘 방문수를 올린 세션
        sess["v_2026-01-01"] = True        # 예전에 쌓인 키
    client.get("/")
    with client.session_transaction() as sess:
        assert not [k for k in sess if k.startswith("v_")]
        assert sess["visited_on"] == today
    with portfolio_app.app_context():
        assert DailyVisit.query.count() == 0


def test_new_day_counts_again(client, portfolio_app, monkeypatch):
    client.get("/")
    monkeypatch.setattr(app_module, "_today_kst", lambda: "2099-01-01")
    client.get("/")
    with portfolio_app.app_context():
        assert {r.date for r in DailyVisit.query.all()} >= {"2099-01-01"}
        assert DailyVisit.query.count() == 2
