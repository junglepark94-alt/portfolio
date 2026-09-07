import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from app import Profile, db  # noqa: E402
import build_general_portfolio_pdf as tool  # noqa: E402


def test_split_kpi_separates_tiles_from_bullets():
    tiles, bullets = tool.split_kpi("568만 | 누적 조회수\n광고 도달 대비 오가닉 증분 +67%\n- 불릿")
    assert tiles == [("568만", "누적 조회수")]
    assert bullets == ["광고 도달 대비 오가닉 증분 +67%", "불릿"]


def test_parse_reads_profile_experience_and_projects_from_rendered_page(client, portfolio_app):
    with portfolio_app.app_context():
        profile = db.session.get(Profile, 1)
        profile.about_text = "소개 문단"
        profile.experience_json = json.dumps([
            {"company": "(주)빙그레", "period": "2022.07 – 현재", "role": "콘텐츠전략팀", "bullets": ["채널 운영", "팝업 기획"]},
            {"company": "(주)CJ ENM", "period": "2019.07 – 2022.03", "role": "조연출", "bullets": ["예능 제작"]},
        ], ensure_ascii=False)
        profile.education_json = json.dumps([{"period": "2013.03 – 2019.08", "school": "고려대학교", "major": "사회학과", "degree": "학사"}], ensure_ascii=False)
        profile.awards_json = json.dumps([{"year": "2025", "title": "대한민국 팝업스토어 어워즈 대상", "org": "팝플리"}], ensure_ascii=False)
        profile.email = "me@example.com"
        db.session.commit()

    html = client.get("/").get_data(as_text=True)
    data = tool.parse(html, "http://testserver", "ko")

    assert data["name"] == "박종걸"
    assert data["about"] == ["소개 문단"]
    assert [e["company"] for e in data["experience"]] == ["(주)빙그레", "(주)CJ ENM"]
    assert data["experience"][0]["bullets"] == ["채널 운영", "팝업 기획"]
    assert data["education"][0]["main"] == "고려대학교"
    assert data["awards"][0]["main"] == "대한민국 팝업스토어 어워즈 대상"
    assert data["email"] == "me@example.com"
    assert len(data["projects"]) == 1
    assert "Banana Salon" in data["projects"][0]["title"]
    assert "67–82%" in data["projects"][0]["kpi"]
