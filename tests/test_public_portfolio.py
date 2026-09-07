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
        project.my_role = "오가닉 유입의 6782%가 구독 피드에서 발생"
        project.period = "2026.07 ~ 진행 중"
        db.session.commit()

        normalize_public_content()
        normalize_public_content()

        assert profile.name_en == "Jonggeol Park"
        assert "I build fandom through content" in profile.tagline_en
        assert profile.skills_en == "Content Strategy & Production,Digital Content,Data Analysis"
        assert project.title == "tvN 예능 ‘샤이니의 빛돌기획’ 제작"
        assert project.category_en == "Content Strategy & Production"
        assert "67–82%" in project.my_role
        assert project.period == "2026.07 – 진행 중"


def test_period_normalization_unifies_dashes_and_stray_spaces():
    from app import _normalize_period

    assert _normalize_period("2022.08 - 2023.12") == "2022.08 – 2023.12"
    assert _normalize_period("2013.03~2019.08") == "2013.03 – 2019.08"
    assert _normalize_period("2010.03-2013.02") == "2010.03 – 2013.02"
    assert _normalize_period("2025.05 – 2025. 11") == "2025.05 – 2025.11"
    assert _normalize_period("2022.07 - 현재") == "2022.07 – 현재"
    assert _normalize_period("2022.07 - Present") == "2022.07 – Present"
    assert _normalize_period("2025.07.17 – 2025.07.27") == "2025.07.17 – 2025.07.27"
    assert _normalize_period("2026.07 – 진행 중") == "2026.07 – 진행 중"


def test_public_content_normalization_fixes_deployed_profile_copy(portfolio_app):
    import json

    with portfolio_app.app_context():
        profile = db.session.get(Profile, 1)
        profile.experience_en_json = json.dumps([
            {"company": "CJ ENM", "period": "2019.07 - 2022.03",
             "role": "Producer / AC (Assitant Creator)",
             "details": ["Credits include: Mountain Village Women"]},
        ], ensure_ascii=False)
        profile.education_json = json.dumps(
            [{"school": "고려대학교", "period": "2013.03~2019.08"}], ensure_ascii=False)
        profile.awards_en_json = json.dumps(
            [{"year": "2025", "title": "2025 Korea Pop-Up Store Awards", "org": "Popply"}],
            ensure_ascii=False)
        project = Project.query.first()
        project.my_role_en = "Planning & Operations Planning & Operations Lead, Agency Management"
        project.title = "빙그레X더현대서울 팝업스토어 기획·운영"
        project.title_en = "tvN Variety Program Production – City girls on the climb"
        project.period = "2025.05 – 2025. 11"
        project.my_role = "Winner of the 2025 Korea Pop-Up Store Awards Grand Prize – Grand Prize"
        profile.about_text_en = "It won the Grand Prize at the 2025 Korea Pop-Up Store Awards Grand Prize, receiving recognition."
        db.session.commit()

        normalize_public_content()
        normalize_public_content()

        exp = profile.experience_en[0]
        assert exp["period"] == "2019.07 – 2022.03"
        assert exp["role"] == "Producer / AC (Assistant Creator)"
        assert profile.education[0]["period"] == "2013.03 – 2019.08"
        assert profile.awards_en[0]["title"] == "2025 Korea Pop-Up Store Awards Grand Prize"
        assert project.my_role_en == "Planning & Operations Lead, Agency Management"
        assert project.title == "빙그레×더현대서울 팝업스토어 기획·운영"
        assert project.title_en == "tvN Variety Program Production – City Girls on the Climb"
        assert project.period == "2025.05 – 2025.11"
        assert project.my_role == "Winner of the 2025 Korea Pop-Up Store Awards – Grand Prize"
        assert profile.about_text_en == "It won the Grand Prize at the 2025 Korea Pop-Up Store Awards, receiving recognition."


def test_project_copy_overrides_apply_canonical_modal_content(portfolio_app):
    import json

    with portfolio_app.app_context():
        project = Project.query.first()
        project.kpi = "본편 8편 누적 조회수 568만회"
        project.detail_text = "줄글 설명"
        project.links_json = json.dumps([{"label": "영상 링크", "url": "https://youtu.be/x"}], ensure_ascii=False)
        project.links_en_json = json.dumps([{"label": "Introduction Video", "url": "https://youtu.be/x"}], ensure_ascii=False)
        db.session.commit()

        normalize_public_content()
        normalize_public_content()

        assert project.kpi.startswith("568만 | ")
        assert project.detail_text.startswith("## 배경과 과제")
        assert project.kpi_en.startswith("5.68M | ")
        assert "## Background & Challenge" in project.detail_text_en
        assert "67–82%" in project.kpi and "67–82%" in project.kpi_en
        # Banana Salon entry defines no link relabels, so links stay as they were
        assert json.loads(project.links_json)[0]["label"] == "영상 링크"


def test_site_projects_file_is_well_formed():
    import json

    data = json.load(open("data/site_projects.json", encoding="utf-8"))
    matches = [p["match"] for p in data["projects"]]
    assert len(matches) == 10 and len(set(matches)) == 10
    for entry in data["projects"]:
        for field in ("description", "kpi", "detail_text", "description_en", "kpi_en", "detail_text_en"):
            assert entry[field].strip(), (entry["match"], field)
        assert "## " in entry["detail_text"] and "## " in entry["detail_text_en"]
        assert "|" in entry["kpi"] and "|" in entry["kpi_en"]


def test_youtube_thumbnail_swap_replaces_only_mapped_images(portfolio_app, monkeypatch):
    import app as app_module
    from app import ProjectImage

    calls = []

    def fake_fetch(video_id):
        calls.append(video_id)
        return f"yt_{video_id}.jpg"

    monkeypatch.setattr(app_module, "_fetch_youtube_thumbnail", fake_fetch)

    with portfolio_app.app_context():
        project = Project.query.first()
        project.title = "글로벌 유튜브 브랜디드 콘텐츠 <Banana Salon> 기획"
        cropped = ProjectImage(project_id=project.id, filename="proj16_1788758649.jpg",
                               is_main=True, sort_order=0)
        untouched = ProjectImage(project_id=project.id, filename="site_photo.jpg", sort_order=1)
        db.session.add_all([cropped, untouched])
        db.session.commit()

        normalize_public_content()
        normalize_public_content()

        assert cropped.filename == "yt_F3AqCokSrTw.jpg"
        assert untouched.filename == "site_photo.jpg"
        # 두 번째 실행에서는 교체할 대상이 남아 있지 않아 다시 내려받지 않는다
        assert calls == ["F3AqCokSrTw"]


def test_youtube_thumbnail_fetch_rejects_placeholder_and_non_images(tmp_path, monkeypatch):
    import app as app_module

    class FakeResponse:
        def __init__(self, payload):
            self.status = 200
            self._payload = payload

        def read(self, *_):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    app_module.app.config["UPLOAD_FOLDER"] = str(tmp_path)
    payloads = {"maxresdefault": b"\xff\xd8\xff" + b"x" * 200, "hqdefault": b"\xff\xd8\xff" + b"y" * 20000}
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=0: FakeResponse(
                            payloads["maxresdefault"] if "maxresdefault" in url else payloads["hqdefault"]))

    # maxresdefault가 작은 자리표시자면 건너뛰고 hqdefault를 저장한다
    assert app_module._fetch_youtube_thumbnail("F3AqCokSrTw") == "yt_F3AqCokSrTw.jpg"
    assert (tmp_path / "yt_F3AqCokSrTw.jpg").read_bytes() == payloads["hqdefault"]
    # 잘못된 형식의 영상 id는 네트워크 요청 없이 거부한다
    assert app_module._fetch_youtube_thumbnail("../../etc/passwd") is None
    assert app_module._fetch_youtube_thumbnail("") is None


def test_canonical_sync_runs_once_and_keeps_admin_edits_afterwards(portfolio_app):
    from app import ContentSync, sync_canonical_content_once

    with portfolio_app.app_context():
        project = Project.query.first()
        project.kpi = "임시 성과"
        db.session.commit()

        assert sync_canonical_content_once() is True
        assert project.kpi.startswith("568만 | ")          # 최초 1회는 기준 문안 적용
        assert db.session.get(ContentSync, "seed_version").value.isdigit()

        project.kpi = "관리자가 고친 성과"
        project.detail_text = "관리자가 고친 상세"
        db.session.commit()

        assert sync_canonical_content_once() is False       # 두 번째부터는 건드리지 않는다
        assert project.kpi == "관리자가 고친 성과"
        assert project.detail_text == "관리자가 고친 상세"


def test_admin_can_reimport_canonical_copy_for_one_project(portfolio_app):
    from app import _apply_copy_entry, _find_copy_entry

    with portfolio_app.app_context():
        project = Project.query.first()
        project.kpi = "관리자가 고친 성과"
        db.session.commit()

        entry = _find_copy_entry(project.title)
        assert entry and entry["match"] == "Banana Salon"
        _apply_copy_entry(project, entry)
        db.session.commit()
        assert project.kpi.startswith("568만 | ")
        assert _find_copy_entry("전혀 다른 프로젝트") is None


def test_thumbnail_swaps_still_run_after_seed_marker_is_set(portfolio_app, monkeypatch):
    import app as app_module
    from app import ProjectImage, apply_youtube_thumbnail_swaps, sync_canonical_content_once

    monkeypatch.setattr(app_module, "_fetch_youtube_thumbnail", lambda vid: f"yt_{vid}.jpg")

    with portfolio_app.app_context():
        assert sync_canonical_content_once() is True      # 기준 문안은 이미 적용된 상태
        project = Project.query.first()
        project.title = "글로벌 유튜브 브랜디드 콘텐츠 <World War Chef>"
        img = ProjectImage(project_id=project.id, filename="proj10_1779436178.jpg", is_main=True)
        db.session.add(img)
        db.session.commit()

        assert sync_canonical_content_once() is False     # 문안은 더 이상 건드리지 않지만
        apply_youtube_thumbnail_swaps()                    # 새 썸네일 매핑은 적용된다
        assert img.filename == "yt_U_kFCUJy_wM.jpg"
