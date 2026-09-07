from app import display_period


def test_display_period_localizes_ongoing_label():
    assert display_period("2026.07 – 진행 중", "ko") == "2026.07 – 진행 중"
    assert display_period("2026.07 – 진행 중", "en") == "2026.07 – Present"


def test_english_page_is_localized_and_preserves_metric_ranges(client):
    html = client.get("/en").get_data(as_text=True)

    assert "Key results" in html
    assert "Project details" in html
    assert "View details" in html
    assert 'aria-label="Close project details"' in html
    assert 'aria-label="Previous image"' in html
    assert 'aria-label="Next image"' in html
    assert "2026.07 – Present" in html
    assert "67–82%" in html
    assert "핵심 성과" not in html
    assert "상세 설명" not in html
    assert "진행 중" not in html


def test_project_cards_are_keyboard_operable_and_admin_link_is_private(client):
    html = client.get("/").get_data(as_text=True)

    assert 'class="project-card' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert 'aria-haspopup="dialog"' in html
    assert "footer-admin-btn" not in html
    assert ">관리자<" not in html


def test_javascript_restores_focus_and_handles_keyboard_activation():
    js = open("static/js/main.js", encoding="utf-8").read()

    assert "activeProjectCard" in js
    assert "activeProjectCard.focus()" in js
    assert "e.key === 'Enter'" in js
    assert "e.key === ' '" in js

