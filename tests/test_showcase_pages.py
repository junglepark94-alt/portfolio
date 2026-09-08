import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import showcase_pages  # noqa: E402


DATA_PATH = Path(__file__).parents[1] / "data" / "hyundai_application_2026.json"


def test_load_showcase_content_reads_all_sections_from_the_real_data_file():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    content = showcase_pages.load_showcase_content(data)

    assert len(content["experience_map"]) == 4
    assert content["experience_map"][0]["eyebrow"] == "01 · DOMESTIC BRAND IP"
    assert content["experience_map"][0]["heading"] == "국내 캐릭터 IP 채널"
    assert "목적:" in content["experience_map"][0]["body"]

    assert len(content["working_method"]) == 3
    assert content["working_method"][0]["step"] == "01"
    assert content["working_method"][0]["label"] == "DEFINE"
    assert content["working_method"][0]["evidence"]

    assert content["portfolio_summary"]["organic_subscribers"] == "10만+"
    assert content["production_titles"] == ["산꾼도시여자들", "샤이니의 빛돌기획"]


def test_load_showcase_content_names_the_missing_key():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    del data["working_method"]

    with pytest.raises(KeyError, match="working_method"):
        showcase_pages.load_showcase_content(data)


def test_split_projects_separates_production_titles_and_keeps_site_order():
    projects = [
        {"title": "글로벌 유튜브 브랜디드 콘텐츠 〈Banana Salon〉 기획"},
        {"title": "산꾼도시여자들"},
        {"title": "빙그레우스 유튜브 채널"},
        {"title": "샤이니의 빛돌기획"},
    ]

    main, production, missing = showcase_pages.split_projects(
        projects, ["산꾼도시여자들", "샤이니의 빛돌기획"])

    assert [p["title"] for p in main] == [
        "글로벌 유튜브 브랜디드 콘텐츠 〈Banana Salon〉 기획",
        "빙그레우스 유튜브 채널",
    ]
    assert [p["title"] for p in production] == ["산꾼도시여자들", "샤이니의 빛돌기획"]
    assert missing == []


def test_split_projects_normalises_whitespace_when_matching():
    projects = [{"title": "샤이니의   빛돌기획 "}, {"title": "다른 프로젝트"}]

    main, production, missing = showcase_pages.split_projects(
        projects, ["샤이니의 빛돌기획"])

    assert [p["title"] for p in production] == ["샤이니의   빛돌기획 "]
    assert [p["title"] for p in main] == ["다른 프로젝트"]
    assert missing == []


def test_split_projects_reports_titles_the_site_does_not_have():
    projects = [{"title": "다른 프로젝트"}]

    main, production, missing = showcase_pages.split_projects(projects, ["없는 제목"])

    assert production == []
    assert [p["title"] for p in main] == ["다른 프로젝트"]
    assert missing == ["없는 제목"]


def test_card_grid_lays_cards_left_to_right_top_row_first():
    cells = showcase_pages.card_grid(0, 0, 100, 100, cols=2, rows=2, gap=10)

    assert len(cells) == 4
    assert cells[0] == (0.0, 55.0, 45.0, 45.0)     # top-left
    assert cells[1] == (55.0, 55.0, 45.0, 45.0)    # top-right
    assert cells[2] == (0.0, 0.0, 45.0, 45.0)      # bottom-left
    assert cells[3] == (55.0, 0.0, 45.0, 45.0)     # bottom-right


def test_card_grid_single_row_splits_width_only():
    cells = showcase_pages.card_grid(44, 200, 700, 140, cols=4, rows=1, gap=16)

    assert len(cells) == 4
    assert cells[0] == (44.0, 200.0, 163.0, 140.0)
    assert cells[3][0] == 44.0 + 3 * (163.0 + 16)
    assert all(cell[3] == 140.0 for cell in cells)


@pytest.fixture
def scratch_canvas(tmp_path):
    from reportlab.pdfgen import canvas as rl_canvas

    showcase_pages.ensure_fonts_for_tests()
    return rl_canvas.Canvas(str(tmp_path / "scratch.pdf"))


def test_draw_text_wraps_at_the_given_width(scratch_canvas):
    # 10pt Nanum CJK glyphs are one em wide, so a 100pt box holds 10 per line.
    end_y, lines = showcase_pages.draw_text(
        scratch_canvas, "가" * 25, 0, 500, 100, size=10, leading=16)

    assert lines == 3
    assert end_y == 468.0          # 500 - 16 * 2


def test_draw_text_starts_a_new_line_at_each_newline(scratch_canvas):
    end_y, lines = showcase_pages.draw_text(
        scratch_canvas, "가\n나\n다", 0, 500, 100, size=10, leading=16)

    assert lines == 3
    assert end_y == 468.0


def test_draw_text_respects_max_lines(scratch_canvas):
    end_y, lines = showcase_pages.draw_text(
        scratch_canvas, "가" * 500, 0, 500, 100, size=10, leading=16, max_lines=3)

    assert lines == 3
    assert end_y == 468.0
