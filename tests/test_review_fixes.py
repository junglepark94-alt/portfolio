import io
import os
from types import SimpleNamespace

import pytest

import app as app_module
from app import Admin, DailyVisit, GalleryItem, Profile, Project, ProjectImage, db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    app_module._RATE_HITS.clear()
    yield tmp_path
    app_module._RATE_HITS.clear()


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


# ── 업로드 파일명 ────────────────────────────────────────

def test_images_uploaded_in_the_same_second_get_distinct_files(client, portfolio_app, isolated_uploads, monkeypatch):
    _login(client)
    # app 모듈이 보는 시계만 멈춘다 (전역 time.time을 바꾸면 세션 쿠키까지 영향을 받는다)
    monkeypatch.setattr(app_module, "time", SimpleNamespace(time=lambda: 1_700_000_000))
    with portfolio_app.app_context():
        pid = Project.query.first().id

    for _ in range(2):
        resp = client.post(f"/admin/project/{pid}/images/upload",
                           data={"image": (io.BytesIO(PNG), "a.png")},
                           content_type="multipart/form-data")
        assert resp.status_code == 200

    with portfolio_app.app_context():
        names = [img.filename for img in ProjectImage.query.filter_by(project_id=pid)]
    assert len(names) == 2 and len(set(names)) == 2
    assert sorted(os.listdir(isolated_uploads)) == sorted(names)


# ── 공유 썸네일 삭제 ─────────────────────────────────────

def test_deleting_a_project_keeps_thumbnails_another_project_still_uses(client, portfolio_app, isolated_uploads):
    _login(client)
    (isolated_uploads / "yt_shared00000.jpg").write_bytes(PNG)
    (isolated_uploads / "proj_own.jpg").write_bytes(PNG)
    with portfolio_app.app_context():
        doomed = Project.query.first()
        other = Project(title="다른 프로젝트", description="d")
        db.session.add(other)
        db.session.flush()
        db.session.add_all([
            ProjectImage(project_id=doomed.id, filename="yt_shared00000.jpg"),
            ProjectImage(project_id=doomed.id, filename="proj_own.jpg"),
            ProjectImage(project_id=other.id, filename="yt_shared00000.jpg"),
        ])
        db.session.commit()
        doomed_id = doomed.id

    client.post(f"/admin/project/{doomed_id}/delete")

    assert (isolated_uploads / "yt_shared00000.jpg").exists()
    assert not (isolated_uploads / "proj_own.jpg").exists()


def test_deleting_an_image_row_keeps_a_file_shared_with_another_row(client, portfolio_app, isolated_uploads):
    _login(client)
    (isolated_uploads / "ext_abc.jpg").write_bytes(PNG)
    with portfolio_app.app_context():
        pid = Project.query.first().id
        first = ProjectImage(project_id=pid, filename="ext_abc.jpg", is_main=True)
        second = ProjectImage(project_id=pid, filename="ext_abc.jpg")
        db.session.add_all([first, second])
        db.session.commit()
        first_id, second_id = first.id, second.id

    client.post(f"/admin/project/images/{first_id}/delete")
    assert (isolated_uploads / "ext_abc.jpg").exists()

    client.post(f"/admin/project/images/{second_id}/delete")
    assert not (isolated_uploads / "ext_abc.jpg").exists()


def test_deleting_a_gallery_item_removes_its_unshared_file(client, portfolio_app, isolated_uploads):
    _login(client)
    (isolated_uploads / "placeholder.jpg").write_bytes(PNG)
    with portfolio_app.app_context():
        gid = GalleryItem.query.first().id

    client.post(f"/admin/gallery/{gid}/delete")

    assert not (isolated_uploads / "placeholder.jpg").exists()


# ── 문안 정리 ───────────────────────────────────────────

def test_social_i_awards_normalization_does_not_double_the_plural():
    from app import _normalize_copy

    assert _normalize_copy("Social I Awards") == "Social i Awards"
    assert _normalize_copy("Social I Award") == "Social i Awards"
    assert _normalize_copy("Social Eye Awards") == "Social i Awards"
    assert _normalize_copy(_normalize_copy("Social I Awards")) == "Social i Awards"


def test_profile_fix_rerun_keeps_admin_edited_hero_copy(portfolio_app):
    from app import ContentSync, apply_profile_fixes_once, sync_canonical_content_once

    with portfolio_app.app_context():
        sync_canonical_content_once()
        profile = db.session.get(Profile, 1)
        profile.role = "관리자가 고친 직무"
        profile.tagline = "관리자가 고친 소개"
        profile.role_en = "Admin role"
        profile.name_en = "Admin Name"
        db.session.query(ContentSync).filter_by(key="profile_fix_version").delete()
        db.session.commit()

        assert apply_profile_fixes_once() is True
        assert profile.role == "관리자가 고친 직무"
        assert profile.tagline == "관리자가 고친 소개"
        assert profile.role_en == "Admin role"
        assert profile.name_en == "Admin Name"


def test_initial_seed_still_applies_canonical_hero_copy(portfolio_app):
    from app import _load_canonical_application, sync_canonical_content_once

    site_copy = _load_canonical_application()["site_copy"]
    with portfolio_app.app_context():
        assert sync_canonical_content_once() is True
        profile = db.session.get(Profile, 1)
        assert profile.role == site_copy["hero_role_ko"]
        assert profile.tagline_en == site_copy["hero_tagline_en"]


# ── 로그인·레이트리밋 ────────────────────────────────────

def test_spoofed_forwarded_for_values_cannot_bypass_the_login_limit(client):
    # 실제 배포에서는 Railway 프록시가 접속 IP를 마지막에 붙인다
    statuses = [
        client.post("/admin/login", data={"username": "x", "password": "y"},
                    headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code
        for i in range(11)
    ]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


def test_login_with_missing_fields_shows_the_form_instead_of_400(client):
    resp = client.post("/admin/login", data={})
    assert resp.status_code == 200


def test_login_starts_a_fresh_session(client, portfolio_app):
    with portfolio_app.app_context():
        admin = Admin(username="admin")
        admin.set_password("pw-for-test")
        db.session.add(admin)
        db.session.commit()
    with client.session_transaction() as sess:
        sess["planted"] = "value-from-before-login"

    resp = client.post("/admin/login", data={"username": "admin", "password": "pw-for-test"})

    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True
        assert "planted" not in sess


# ── 방문수 ──────────────────────────────────────────────

def test_daily_visit_increments_in_the_database(portfolio_app):
    from app import increment_daily_visit

    with portfolio_app.app_context():
        assert increment_daily_visit("2026-10-27") is True
        assert increment_daily_visit("2026-10-27") is True
        db.session.add(DailyVisit(date="2026-10-28", count=None))
        db.session.commit()
        increment_daily_visit("2026-10-28")

        counts = {r.date: r.count for r in DailyVisit.query.all()}
    assert counts == {"2026-10-27": 2, "2026-10-28": 1}


def test_daily_visit_increment_survives_a_concurrent_first_insert(portfolio_app, monkeypatch):
    """다른 요청이 같은 날짜 행을 먼저 넣어 INSERT가 실패해도 그 행을 올려 1을 잃지 않는다."""
    from app import increment_daily_visit

    with portfolio_app.app_context():
        real_update = app_module.DailyVisit.query.filter_by(date="2026-10-29").update.__func__
        calls = {"n": 0}

        def racing_update(self, values, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                # 첫 UPDATE 직후 다른 요청이 같은 날짜 행을 넣은 상황
                with db.engine.begin() as conn:
                    conn.execute(db.text(
                        "INSERT INTO daily_visit (date, count) VALUES ('2026-10-29', 1)"))
                return 0
            return real_update(self, values, **kwargs)

        monkeypatch.setattr(type(DailyVisit.query), "update", racing_update)
        assert increment_daily_visit("2026-10-29") is True
        monkeypatch.undo()

        assert DailyVisit.query.filter_by(date="2026-10-29").one().count == 2


# ── 폼 입력 ─────────────────────────────────────────────

def test_blank_order_field_saves_as_zero_instead_of_500(client, portfolio_app):
    _login(client)
    resp = client.post("/admin/project/new", data={
        "title": "새 프로젝트", "description": "d", "tech_stack": "", "order": "",
    })
    assert resp.status_code == 302
    with portfolio_app.app_context():
        assert Project.query.filter_by(title="새 프로젝트").one().order == 0


def test_reorder_with_a_malformed_body_does_not_500(client):
    _login(client)
    resp = client.post("/admin/projects/reorder", data="not json",
                       content_type="application/json")
    assert resp.status_code == 200


def test_upload_queue_continues_after_a_non_json_error():
    html = open("templates/project_form.html", encoding="utf-8").read()
    assert "r.json().catch(" in html
    assert "if (data.error) alert(data.error);" in html


# ── JSON 속성 ───────────────────────────────────────────

def test_json_properties_tolerate_broken_or_missing_values(portfolio_app):
    with portfolio_app.app_context():
        profile = db.session.get(Profile, 1)
        profile.awards_json = "{not json"
        profile.tools_json = None
        profile.skills = None
        assert profile.awards == []
        assert profile.tools == []
        assert profile.skill_list == []
