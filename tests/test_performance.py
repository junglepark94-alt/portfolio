import io
import os

import pytest
from PIL import Image

import app as app_module
import images as images_mod
from app import GalleryItem, Profile, Project, ProjectImage, db


@pytest.fixture()
def uploads(tmp_path, monkeypatch, portfolio_app):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    return tmp_path


def _photo(path, size=(2400, 1350), fmt="JPEG"):
    # 압축이 잘 안 되는 무늬를 넣어 실제 사진처럼 큰 파일을 만든다
    img = Image.effect_noise(size, 64).convert("RGB")
    img.save(path, fmt, quality=95)
    return path


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


# ── 축소본 생성 ────────────────────────────────────────

def test_resized_variant_is_smaller_webp_at_requested_width(client, uploads):
    _photo(uploads / "proj1_big.jpg")
    resp = client.get("/media/480/proj1_big.jpg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/webp"
    assert "immutable" in resp.headers["Cache-Control"]
    img = Image.open(io.BytesIO(resp.data))
    assert img.width == 480 and img.height == 270
    assert len(resp.data) < os.path.getsize(uploads / "proj1_big.jpg") / 5


def test_variant_is_cached_on_disk_and_reused(client, uploads, monkeypatch):
    _photo(uploads / "a.jpg")
    assert client.get("/media/960/a.jpg").status_code == 200
    cached = uploads / "_resized" / images_mod.VARIANT_VERSION / "960" / "a.webp"
    assert cached.exists()

    monkeypatch.setattr(images_mod.Image, "open", lambda *a, **k: pytest.fail("should reuse cached file"))
    assert client.get("/media/960/a.jpg").status_code == 200


def test_small_images_are_not_upscaled(client, uploads):
    _photo(uploads / "small.png", size=(300, 200), fmt="PNG")
    img = Image.open(io.BytesIO(client.get("/media/1600/small.png").data))
    assert img.size == (300, 200)


def test_png_transparency_is_kept(client, uploads):
    Image.new("RGBA", (800, 400), (255, 0, 0, 0)).save(uploads / "logo.png")
    img = Image.open(io.BytesIO(client.get("/media/480/logo.png").data))
    assert img.mode == "RGBA" and img.getpixel((0, 0))[3] == 0


def test_gif_is_served_as_original(client, uploads):
    Image.new("P", (100, 100)).save(uploads / "anim.gif")
    resp = client.get("/media/480/anim.gif")
    assert resp.status_code == 200
    assert resp.data == (uploads / "anim.gif").read_bytes()


def test_corrupt_image_falls_back_to_original(client, uploads):
    (uploads / "broken.jpg").write_bytes(b"\xff\xd8\xff" + b"garbage" * 10)
    resp = client.get("/media/480/broken.jpg")
    assert resp.status_code == 200
    assert resp.data == (uploads / "broken.jpg").read_bytes()


@pytest.mark.parametrize("url", ["/media/123/a.jpg", "/media/480/missing.jpg", "/media/480/..%2Fapp.py"])
def test_bad_requests_return_404(client, uploads, url):
    _photo(uploads / "a.jpg", size=(600, 400))
    assert client.get(url).status_code == 404


def test_deleting_an_upload_removes_its_variants(client, portfolio_app, uploads):
    _login(client)
    _photo(uploads / "placeholder.jpg", size=(1200, 675))
    client.get("/media/480/placeholder.jpg")
    variant = uploads / "_resized" / images_mod.VARIANT_VERSION / "480" / "placeholder.webp"
    assert variant.exists()
    gid = GalleryItem.query.first().id
    client.post(f"/admin/gallery/{gid}/delete")
    assert not (uploads / "placeholder.jpg").exists()
    assert not variant.exists()


def test_warm_variants_builds_every_size_for_referenced_images(portfolio_app, uploads):
    project = Project.query.first()
    db.session.add(ProjectImage(project_id=project.id, filename="p.jpg", is_main=True))
    db.session.get(Profile, 1).profile_image_filename = "me.jpg"
    db.session.commit()
    _photo(uploads / "p.jpg", size=(2000, 1125))
    _photo(uploads / "me.jpg", size=(700, 900))
    # placeholder.jpg(갤러리)는 파일이 없으므로 건너뛴다
    assert images_mod.warm_variants() == 6
    assert images_mod.warm_variants() == 0


# ── 공개 페이지가 축소본을 쓰는지 ─────────────────────────

def test_public_page_uses_resized_images(client, portfolio_app):
    project = Project.query.first()
    db.session.add(ProjectImage(project_id=project.id, filename="card.jpg", is_main=True))
    db.session.get(Profile, 1).profile_image_filename = "me.png"
    db.session.commit()
    html = client.get("/").get_data(as_text=True)
    assert 'src="/media/480/card.jpg"' in html
    assert "/media/960/card.jpg 960w" in html
    assert 'src="/media/480/me.png"' in html and 'fetchpriority="high"' in html
    assert 'src="/media/480/placeholder.jpg"' in html          # 갤러리 카드
    assert "/static/uploads/card.jpg" not in html


# ── CSS·JS 캐시 ───────────────────────────────────────

def test_static_assets_get_version_and_long_cache(client):
    html = client.get("/").get_data(as_text=True)
    css = next(part for part in html.split('"') if part.startswith("/static/css/main.css"))
    assert "?v=" in css
    resp = client.get(css)
    assert resp.status_code == 200
    assert "max-age=31536000" in resp.headers["Cache-Control"]
    unversioned = client.get("/static/css/main.css")
    assert "max-age=31536000" not in unversioned.headers.get("Cache-Control", "")


def test_fonts_stylesheet_does_not_block_rendering(client):
    html = client.get("/").get_data(as_text=True)
    assert 'rel="preload" as="style"' in html
    assert '<link href="https://fonts.googleapis.com' not in html
