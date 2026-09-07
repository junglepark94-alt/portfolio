from app import Profile, Project, db, display_period, normalize_public_content


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


def test_public_content_normalization_is_targeted_and_idempotent(portfolio_app):
    with portfolio_app.app_context():
        profile = db.session.get(Profile, 1)
        profile.name_en = "Jong Geol Park"
        profile.tagline_en = "From PD to marketer — crafting strategies only someone who knows both worlds can."
        profile.skills_en = "Contents Planning,Digital Contents,Data Analysis"
        project = Project.query.first()
        project.title = "tvN 예능 프로그램 제작 – 사이니의 빛돌기획"
        project.category_en = "Contents Planning"
        project.kpi = "오가닉 유입의 6782%가 구독 피드에서 발생"
        project.period = "2026.07 ~ 진행 중"
        db.session.commit()

        normalize_public_content()
        normalize_public_content()

        assert profile.name_en == "Jonggeol Park"
        assert "I build fandom through content" in profile.tagline_en
        assert profile.skills_en == "Content Strategy & Production,Digital Content,Data Analysis"
        assert project.title == "tvN 예능 ‘샤이니의 빛돌기획’ 제작"
        assert project.category_en == "Content Strategy & Production"
        assert "67–82%" in project.kpi
        assert project.period == "2026.07 – 진행 중"
