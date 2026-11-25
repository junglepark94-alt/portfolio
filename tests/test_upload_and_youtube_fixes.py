import io
import json
import urllib.request

import pytest

import app as app_module
import content_sync as content_sync_mod
import schema as schema_mod
import ratelimit as ratelimit_mod
import youtube as youtube_mod
from app import GalleryItem, Profile, db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    ratelimit_mod._RATE_HITS.clear()
    youtube_mod._YT_CACHE.clear()
    yield tmp_path
    ratelimit_mod._RATE_HITS.clear()
    youtube_mod._YT_CACHE.clear()


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


# ── 1. 업로드 폴더 볼륨 확인 ──────────────────────────────

def test_uploads_not_on_volume_without_railway_mount(monkeypatch, tmp_path):
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    assert app_module.uploads_on_persistent_volume(str(tmp_path / "uploads")) is False


def test_uploads_on_volume_when_folder_is_inside_mount(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    assert app_module.uploads_on_persistent_volume(str(tmp_path / "uploads")) is True
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path / "other"))
    assert app_module.uploads_on_persistent_volume(str(tmp_path / "uploads")) is False


def test_admin_shows_uploads_warning_in_production(client, monkeypatch):
    _login(client)
    monkeypatch.setattr(app_module, "_is_production", True)
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    html = client.get("/admin").get_data(as_text=True)
    assert "업로드 저장소 경고" in html


# ── 2. YouTube 응답 캐시 ─────────────────────────────────

class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _video_payload():
    return {"items": [{"snippet": {"title": "T", "thumbnails": {"high": {"url": "https://i.ytimg.com/x.jpg"}}},
                       "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"}}]}


def test_youtube_info_is_cached(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResp(json.dumps(_video_payload()).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    for _ in range(3):
        resp = client.get("/api/youtube?v=abcdefghijk")
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "T"
    assert len(calls) == 1


def test_youtube_cache_hits_do_not_count_against_rate_limit(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResp(json.dumps(_video_payload()).encode()))
    for _ in range(40):  # 레이트리밋 한도(30)보다 많이
        assert client.get("/api/youtube?v=abcdefghijk").status_code == 200


def test_youtube_errors_are_not_cached_and_do_not_leak_details(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    calls = []

    def boom(url, timeout=None):
        calls.append(url)
        raise OSError("secret detail with key=test-key")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    for _ in range(2):
        resp = client.get("/api/youtube?v=abcdefghijk")
        assert resp.status_code == 500
        assert "test-key" not in resp.get_data(as_text=True)
    assert len(calls) == 2


def test_playlist_with_no_playable_videos_returns_404(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    responses = iter([
        {"items": [{"contentDetails": {"videoId": "abcdefghijk"}}]},
        {"items": []},  # 비공개/삭제된 영상만 남은 재생목록
    ])
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResp(json.dumps(next(responses)).encode()))
    assert client.get("/api/youtube/playlist?list=PLabcdefghij").status_code == 404


# ── 3. 부팅 중 네트워크 작업은 백그라운드로 ──────────────────

def test_init_db_runs_network_tasks_in_background(portfolio_app, monkeypatch):
    started = []
    monkeypatch.setattr(schema_mod, "start_boot_network_tasks", lambda: started.append(True))
    monkeypatch.setattr(schema_mod, "run_boot_network_tasks",
                        lambda: pytest.fail("network tasks must not block boot"))
    with portfolio_app.app_context():
        app_module.init_db()
    assert started == [True]


def test_background_network_thread_runs_tasks(portfolio_app, monkeypatch):
    ran = []
    monkeypatch.setattr(content_sync_mod, "run_boot_network_tasks", lambda: ran.append(True))
    content_sync_mod.start_boot_network_tasks().join(timeout=5)
    assert ran == [True]


# ── 4. 교체된 업로드 파일 정리 + PDF 검사 ───────────────────

def test_replacing_profile_image_removes_old_file(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "profile_old.png").write_bytes(PNG)
    with portfolio_app.app_context():
        db.session.get(Profile, 1).profile_image_filename = "profile_old.png"
        db.session.commit()

    resp = client.post("/admin/profile", data={"profile_image_file": (io.BytesIO(PNG), "new.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    with portfolio_app.app_context():
        new_name = db.session.get(Profile, 1).profile_image_filename
    assert new_name != "profile_old.png"
    assert (isolated_state / new_name).exists()
    assert not (isolated_state / "profile_old.png").exists()


def test_replacing_resume_removes_old_pdf(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "resume.pdf").write_bytes(PDF)
    resp = client.post("/admin/profile", data={"resume_file": (io.BytesIO(PDF), "cv.pdf")},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    with portfolio_app.app_context():
        new_name = db.session.get(Profile, 1).resume_filename
    assert new_name != "resume.pdf"
    assert (isolated_state / new_name).exists()
    assert not (isolated_state / "resume.pdf").exists()


def test_fake_pdf_is_rejected_and_old_resume_kept(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "resume.pdf").write_bytes(PDF)
    resp = client.post("/admin/profile", data={"resume_file": (io.BytesIO(b"<html>evil</html>"), "cv.pdf")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert "PDF 파일만" in resp.get_data(as_text=True)
    with portfolio_app.app_context():
        assert db.session.get(Profile, 1).resume_filename == "resume.pdf"
    assert (isolated_state / "resume.pdf").exists()


def test_profile_save_without_new_files_keeps_existing_files(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "resume.pdf").write_bytes(PDF)
    (isolated_state / "og_keep.jpg").write_bytes(PNG)
    with portfolio_app.app_context():
        db.session.get(Profile, 1).og_image_url = "https://example.com/static/uploads/og_keep.jpg"
        db.session.commit()
    client.post("/admin/profile",
                data={"og_image_url": "https://example.com/static/uploads/og_keep.jpg"})
    assert (isolated_state / "resume.pdf").exists()
    assert (isolated_state / "og_keep.jpg").exists()


def test_replacing_og_image_removes_old_upload(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "og_old.png").write_bytes(PNG)
    with portfolio_app.app_context():
        db.session.get(Profile, 1).og_image_url = "https://example.com/static/uploads/og_old.png"
        db.session.commit()
    client.post("/admin/profile", data={"og_image_file": (io.BytesIO(PNG), "og.png")},
                content_type="multipart/form-data")
    assert not (isolated_state / "og_old.png").exists()


def test_replacing_gallery_image_removes_old_file(client, portfolio_app, isolated_state):
    _login(client)
    (isolated_state / "placeholder.jpg").write_bytes(PNG)
    with portfolio_app.app_context():
        gid = GalleryItem.query.first().id
    resp = client.post(f"/admin/gallery/{gid}/edit",
                       data={"title": "현장 기록", "image": (io.BytesIO(PNG), "new.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    assert not (isolated_state / "placeholder.jpg").exists()


def test_upload_name_from_url_ignores_external_and_traversal():
    assert app_module._upload_name_from_url("https://x.com/static/uploads/og_1.jpg") == "og_1.jpg"
    assert app_module._upload_name_from_url("https://cdn.example.com/og.jpg") == ""
    assert app_module._upload_name_from_url("https://x.com/static/uploads/../app.py") == ""
    assert app_module._upload_name_from_url("") == ""
