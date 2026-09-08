import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import astra_pages  # noqa: E402
import build_general_portfolio_pdf as base  # noqa: E402


# A site fixture small enough to render without touching the network.
MINIMAL_SITE_DATA = {
    "name": "박종걸", "role": "브랜드 마케팅", "photo": "", "site": "http://example.test",
    "tagline": "태그라인",
    "skills": [], "tools": [], "highlights": [],
    "lang": "ko", "about": ["소개"], "education": [], "language": [], "awards": [],
    "experience": [], "email": "me@example.test", "linkedin": "",
    "projects": [
        {"title": f"프로젝트 {i}", "period": "2025", "desc": "설명", "detail": "",
         "kpi": "100만 | 조회수", "role": "기획", "category": "콘텐츠",
         "links": [], "images": [], "tags": ""}
        for i in range(1, 4)
    ] + [
        {"title": "tvN 예능 프로그램 제작 – 산꾼도시여자들", "period": "2021", "desc": "설명", "detail": "",
         "kpi": "", "role": "조연출", "category": "제작",
         "links": [], "images": [], "tags": ""},
        {"title": "tvN 예능 ‘샤이니의 빛돌기획’ 제작", "period": "2020", "desc": "설명", "detail": "",
         "kpi": "", "role": "조연출", "category": "제작",
         "links": [], "images": [], "tags": ""},
    ],
}


ASTRA_PATH = Path(__file__).parents[1] / "data" / "astra_portfolio.json"


def _content():
    return astra_pages.load_astra_content(json.loads(ASTRA_PATH.read_text(encoding="utf-8")))


def test_load_astra_content_names_the_missing_section():
    data = json.loads(ASTRA_PATH.read_text(encoding="utf-8"))
    del data["method"]

    with pytest.raises(KeyError, match="method"):
        astra_pages.load_astra_content(data)


def test_every_astra_project_names_a_project_that_exists_on_the_live_site_fixture():
    # The JSON keys projects by site title; a typo there silently drops images and links.
    content = _content()
    titles = [p["site_title"] for p in content["projects"]]
    assert len(titles) == 8
    assert len(set(titles)) == 8
    for card in content["production"]["cards"]:
        assert card["site_title"] not in titles


def test_astra_layout_builds_cover_profile_overview_projects_tail_and_eod(tmp_path):
    from pypdf import PdfReader

    base.ensure_fonts()
    content = _content()
    # Site fixture with the real project titles so the renderer's lookups resolve.
    data = dict(MINIMAL_SITE_DATA)
    data["projects"] = [
        {"title": p["site_title"], "period": "2025", "desc": "설명", "detail": "",
         "kpi": "", "role": "기획", "category": "콘텐츠", "links": [], "images": [], "tags": ""}
        for p in content["projects"]
    ] + [
        {"title": c["site_title"], "period": "2021", "desc": "설명", "detail": "",
         "kpi": "", "role": "조연출", "category": "제작", "links": [], "images": [], "tags": ""}
        for c in content["production"]["cards"]
    ]
    data.setdefault("tagline", ""); data.setdefault("skills", []); data.setdefault("tools", []); data.setdefault("highlights", [])

    out = tmp_path / "astra.pdf"
    base.Doc(str(out), data, base.LABELS["ko"], layout="astra", content=content).build()

    reader = PdfReader(str(out))
    text = "\n".join(pg.extract_text() or "" for pg in reader.pages)

    # cover + profile + overview + 8 projects + production + method + EOD
    assert len(reader.pages) == 14
    assert "PROFILE" in reader.pages[1].extract_text()
    assert "OVERVIEW" in reader.pages[2].extract_text()
    assert "01 / 08" in reader.pages[3].extract_text()
    assert "08 / 08" in reader.pages[10].extract_text()
    assert "PRODUCTION FOUNDATION" in reader.pages[11].extract_text()
    assert "HOW I WORK" in reader.pages[12].extract_text()
    assert "EOD" in reader.pages[13].extract_text()
    assert "4.4만" in text                      # production stat is the contribution metric
    assert "3.339%" not in text                 # not the programme's ratings
    assert "2,400만" in text                    # numbers are never split across lines
