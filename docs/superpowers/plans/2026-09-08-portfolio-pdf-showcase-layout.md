# 포트폴리오 PDF 결합본 (showcase 레이아웃) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `tools/build_general_portfolio_pdf.py`에 `--layout showcase` 모드를 추가해, 편집 디자인이 좋은 인트로·마무리 면과 정보 밀도가 높은 프로젝트 상세 면을 결합한 15페이지 PDF를 만든다.

**Architecture:** 기존 도구를 뼈대로 쓴다. 프로젝트 상세 면 렌더러(`Doc.project`)와 스크레이핑·이미지 캐시·폰트 로직은 **한 줄도 고치지 않는다**. 유지할 정적 7개 면은 새 모듈 `tools/showcase_pages.py`에 순수 렌더 함수로 새로 작성하고, `Doc.build()`가 `layout` 값에 따라 기존 경로와 새 경로 중 하나를 고른다. 편집 카피는 `data/hyundai_application_2026.json`에서 읽는다.

**Tech Stack:** Python 3.12, reportlab 5.0.1, pypdf 6.17.0, Pillow 12.3.0. 테스트는 pytest. 프로젝트 venv는 `.venv/Scripts/python.exe`.

## Global Constraints

- 모든 명령은 프로젝트 venv로 실행한다: `.venv/Scripts/python.exe`
- `tools/build_general_portfolio_pdf.py`의 기존 함수·메서드 본문은 수정 금지. 추가만 허용하며, 예외는 Task 7이 명시하는 `Doc.__init__`, `Doc.build`, `render`, `build`, `__main__` 다섯 지점뿐이다.
- `--layout` 기본값은 `general`. 인자 없이 실행하면 현행 13페이지 출력이 그대로 나와야 한다.
- 폰트는 `Sans` / `SansB` / `Serif` / `SerifB` / `SerifXB` 다섯 이름만 쓴다. `C:/Windows/Fonts` 경로를 새로 참조하지 않는다.
- 색은 `build_general_portfolio_pdf`의 상수(`BG`, `BG_ALT`, `SURFACE`, `BORDER`, `TEXT`, `TEXT_2`, `MUTED`, `ACCENT`)만 쓴다. 새 헥스 리터럴을 만들지 않는다.
- 출력 PDF는 2MB 미만을 유지한다.
- 커밋 메시지 끝에 다음 줄을 붙인다: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

## 참조: 이식할 원본 코드

`tools/build_portfolio_pdf.py`의 아래 구간이 이식 대상이다. 레이아웃 좌표와 구성은 그대로 옮기고, 폰트·색 이름만 아래 대응표로 치환한다.

| 면 | 원본 위치 |
|---|---|
| 커버 | `tools/build_portfolio_pdf.py:250-266` |
| 프로필 | `tools/build_portfolio_pdf.py:268-326` |
| IMPACT | `tools/build_portfolio_pdf.py:328-361` |
| EXPERIENCE MAP | `tools/build_portfolio_pdf.py:363-384` |
| PRODUCTION FOUNDATION | `tools/build_portfolio_pdf.py:427-433` (+ `mini_case` `220-248`) |
| HOW I WORK | `tools/build_portfolio_pdf.py:435-461` |
| 클로징 | `tools/build_portfolio_pdf.py:463-496` |
| 공통 헬퍼 | `draw_text` `97-109`, `draw_image_cover` `110-138`, `eyebrow` `151-160`, `title` `161-177` |

**치환 대응표**

| 원본 | 대체 |
|---|---|
| 폰트 `"Noto"` | `'Sans'` |
| 폰트 `"NotoM"` | `'SansB'` |
| 큰 제목 (size ≥ 17) | `'SerifXB'` |
| 중간 제목 (13 ≤ size < 17) | `'SerifB'` |
| `BG` `#F7F3EA` | `BG` |
| `SURFACE` `#EEE7DA` | `BG_ALT` |
| `WHITE` `#FFFFFF` | `SURFACE` |
| `TEXT` `#29221F` | `TEXT` |
| `MUTED` `#756B64` | `MUTED` |
| `ACCENT` `#C45E3A` | `ACCENT` |
| `ACCENT_DARK` `#8C3F27` | `ACCENT` |
| `LINE` `#D8CCBB` | `BORDER` |
| `page_frame(c, n, section)` | `doc.begin_page()` + `doc.footer(label)` |
| `asset("portrait")` | `cached_image(doc.data['site'], doc.data['photo'], 200, doc.quality)` |

---

### Task 1: 편집 카피를 JSON으로 옮기고 로더를 만든다

**Files:**
- Create: `tools/showcase_pages.py`
- Create: `tests/test_showcase_pages.py`
- Modify: `data/hyundai_application_2026.json`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces: `load_showcase_content(data: dict) -> dict` — `data`는 파싱된 `hyundai_application_2026.json`. 반환 dict는 `experience_map`(4원소 리스트), `working_method`(3원소 리스트), `portfolio_summary`(dict), `production_titles`(문자열 리스트) 키를 가진다. 필수 키가 없으면 `KeyError`를 raise한다.

- [ ] **Step 1: Write the failing test**

`tests/test_showcase_pages.py` 생성:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'showcase_pages'`

- [ ] **Step 3: Add the content keys to the JSON**

`data/hyundai_application_2026.json`의 최상위에 `portfolio_summary` 블록 **바로 뒤**에 세 키를 추가한다. 문구는 `tools/build_portfolio_pdf.py:367-372`의 `map_cards`와 `435-461`의 HOW I WORK 카드에서 그대로 옮긴 것이다.

```json
  "experience_map": [
    {
      "eyebrow": "01 · DOMESTIC BRAND IP",
      "heading": "국내 캐릭터 IP 채널",
      "body": "목적: 검색과 재방문을 통한 팬덤 형성\n방식: 버추얼 캐릭터·연속 세계관·제품 스토리텔링\n성과: 순 시청자 3,255%·재방문 3,617% 증가"
    },
    {
      "eyebrow": "02 · GLOBAL BRAND CHANNEL",
      "heading": "글로벌 수출 브랜드 채널",
      "body": "목적: 국가별 제품 인지도와 오가닉 구독자 확보\n방식: 현지 문화 코드·크리에이터·플랫폼 알고리즘\n성과: 콘텐츠 5,200만+ 조회·수출국 시청 비중 80%+"
    },
    {
      "eyebrow": "03 · BRAND EXPERIENCE",
      "heading": "오프라인 브랜드 경험",
      "body": "목적: 온라인 팬덤을 체험·상품·커머스로 확장\n방식: 세계관 기반 공간·동선·MD·공유 장치 통합\n성과: 방문객 3.3만 명·연계 매출 3.2억 원"
    },
    {
      "eyebrow": "04 · PRODUCTION",
      "heading": "방송·브랜디드 콘텐츠 제작",
      "body": "목적: 출연자의 매력과 프로그램 기대감 극대화\n방식: 기획·촬영·편집·티저·예고·후반 관리\n경험: Mnet·tvN 음악·푸드·야외 버라이어티"
    }
  ],
  "working_method": [
    {
      "step": "01",
      "label": "DEFINE",
      "body": "조회수보다 먼저 고객 행동과 성공 지표를 정의합니다. 검색·재방문·구독·타깃 국가 비중·현장 참여를 목적에 맞게 선택합니다.",
      "evidence": "국내 IP 채널과 글로벌 채널에 서로 다른 KPI 적용"
    },
    {
      "step": "02",
      "label": "DESIGN & DELIVER",
      "body": "인사이트를 포맷, 출연자, 유통, 공간, 상품까지 연결하고 유관부서와 에이전시를 하나의 실행 기준으로 정렬합니다.",
      "evidence": "PD 제작 경험 + 브랜드 캠페인 총괄 경험"
    },
    {
      "step": "03",
      "label": "MEASURE & TOOL",
      "body": "공개 후 데이터를 다음 기획에 반영하고 반복 업무는 도구화합니다. 광고 성과 대시보드와 콘텐츠 수집 자동화 도구를 직접 구현했습니다.",
      "evidence": "분석 속도 향상·사내 뉴스레터 작성 시간 70% 단축"
    }
  ],
  "showcase_production_titles": ["산꾼도시여자들", "샤이니의 빛돌기획"],
```

- [ ] **Step 4: Verify the JSON still parses**

Run: `.venv/Scripts/python.exe -c "import json,io; d=json.load(io.open('data/hyundai_application_2026.json',encoding='utf-8')); print(len(d['experience_map']), len(d['working_method']), d['showcase_production_titles'])"`
Expected: `4 3 ['산꾼도시여자들', '샤이니의 빛돌기획']`

- [ ] **Step 5: Write the loader**

`tools/showcase_pages.py` 생성:

```python
# -*- coding: utf-8 -*-
"""Static page renderers for the `showcase` portfolio PDF layout.

The project detail pages come from build_general_portfolio_pdf.Doc.project and are
not touched here. This module only draws the seven hand-laid-out pages around them:
cover, profile, impact, experience map, production foundation, working method, closing.

Editorial copy lives in data/hyundai_application_2026.json, not in this file.
"""

REQUIRED_KEYS = ("portfolio_summary", "experience_map", "working_method",
                 "showcase_production_titles")


def load_showcase_content(data):
    """Pull the showcase-only copy out of the parsed application JSON.

    Raises KeyError naming the first missing top-level key.
    """
    for key in REQUIRED_KEYS:
        if key not in data:
            raise KeyError(key)
    return {
        "portfolio_summary": data["portfolio_summary"],
        "experience_map": data["experience_map"],
        "working_method": data["working_method"],
        "production_titles": data["showcase_production_titles"],
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add tools/showcase_pages.py tests/test_showcase_pages.py data/hyundai_application_2026.json
git commit -m "feat: move showcase editorial copy into the application JSON

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: 프로젝트를 상세 8개와 제작 2개로 나눈다

**Files:**
- Modify: `tools/showcase_pages.py`
- Test: `tests/test_showcase_pages.py`

**Interfaces:**
- Consumes: Task 1의 `load_showcase_content` (같은 모듈)
- Produces: `split_projects(projects: list[dict], production_titles: list[str]) -> tuple[list[dict], list[dict], list[str]]` — `(main, production, missing)`. `projects`는 스크레이핑된 프로젝트 dict 리스트로 `title` 키를 가진다. `production`은 `production_titles` 순서를 따른다. `main`은 원래 정렬 순서를 유지한다. `missing`은 사이트에서 찾지 못한 제목 리스트다.

- [ ] **Step 1: Write the failing test**

`tests/test_showcase_pages.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: FAIL — `AttributeError: module 'showcase_pages' has no attribute 'split_projects'`

- [ ] **Step 3: Write the implementation**

`tools/showcase_pages.py`의 `load_showcase_content` 아래에 추가:

```python
import re


def _norm(title):
    return re.sub(r"\s+", " ", (title or "")).strip()


def split_projects(projects, production_titles):
    """Split scraped projects into detail-page projects and production mini cards.

    Matching is on the whitespace-normalised title. Returns (main, production, missing);
    `production` follows the order given in `production_titles`.
    """
    wanted = [_norm(t) for t in production_titles]
    by_norm = {}
    for p in projects:
        by_norm.setdefault(_norm(p.get("title")), p)

    production, missing = [], []
    for original, key in zip(production_titles, wanted):
        if key in by_norm:
            production.append(by_norm[key])
        else:
            missing.append(original)

    picked = {id(p) for p in production}
    main = [p for p in projects if id(p) not in picked]
    return main, production, missing
```

파일 상단의 docstring 바로 아래로 `import re`를 옮겨 임포트가 한 곳에 모이게 한다.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add tools/showcase_pages.py tests/test_showcase_pages.py
git commit -m "feat: split scraped projects into detail pages and production cards

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: 카드 격자 좌표 계산기

**Files:**
- Modify: `tools/showcase_pages.py`
- Test: `tests/test_showcase_pages.py`

**Interfaces:**
- Consumes: 없음
- Produces: `card_grid(x, y, width, height, cols, rows, gap) -> list[tuple[float, float, float, float]]` — `(x, y)`는 격자 좌상단이 아니라 **좌하단** 기준(reportlab 좌표계). 반환은 각 칸의 `(x, y, w, h)`이며 좌→우, **위 행부터** 순서로 나열한다.

- [ ] **Step 1: Write the failing test**

`tests/test_showcase_pages.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: FAIL — `AttributeError: module 'showcase_pages' has no attribute 'card_grid'`

- [ ] **Step 3: Write the implementation**

`tools/showcase_pages.py`에 추가:

```python
def card_grid(x, y, width, height, cols, rows, gap):
    """Even card grid inside the given box, listed left-to-right, top row first.

    (x, y) is the bottom-left corner, matching reportlab's coordinate system.
    """
    cell_w = (width - gap * (cols - 1)) / cols
    cell_h = (height - gap * (rows - 1)) / rows
    cells = []
    for row in range(rows):
        top_first = rows - 1 - row
        for col in range(cols):
            cells.append((
                float(x + col * (cell_w + gap)),
                float(y + top_first * (cell_h + gap)),
                float(cell_w),
                float(cell_h),
            ))
    return cells
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add tools/showcase_pages.py tests/test_showcase_pages.py
git commit -m "feat: add card grid geometry helper for showcase pages

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 텍스트 헬퍼와 커버·프로필 면

**Files:**
- Modify: `tools/showcase_pages.py`
- Test: `tests/test_showcase_pages.py`

**Interfaces:**
- Consumes: `card_grid` (Task 3)
- Produces:
  - `draw_text(c, text, x, y, width, size=10, leading=16, font='Sans', color=None, max_lines=None) -> tuple[float, int]` — `(마지막 베이스라인 y, 그린 줄 수)`를 반환한다. `color=None`이면 `TEXT`. 호출부는 대부분 y만 쓰므로 `y, _ = draw_text(...)` 형태로 받는다.
  - `eyebrow(c, text, x, y) -> None`
  - `render_cover(doc, content) -> None`
  - `render_profile(doc, content) -> None`
  - 두 렌더 함수 모두 `doc.begin_page()`로 시작하고 `doc.footer(...)`로 끝난다. `doc`은 `build_general_portfolio_pdf.Doc` 인스턴스다.

- [ ] **Step 1: Write the failing test**

`tests/test_showcase_pages.py` 끝에 추가:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: FAIL — `AttributeError: module 'showcase_pages' has no attribute 'ensure_fonts_for_tests'`

- [ ] **Step 3: Write the text helpers**

`tools/showcase_pages.py`에 추가한다. `LAST_LINE_COUNT`는 줄 수를 검사하기 위한 모듈 전역이다.

```python
from reportlab.pdfbase import pdfmetrics

import build_general_portfolio_pdf as base


def ensure_fonts_for_tests():
    """Register the Nanum faces so canvas helpers can be unit-tested."""
    base.ensure_fonts()


def _wrap(text, width, font, size):
    lines = []
    for paragraph in (text or "").split("\n"):
        line = ""
        for ch in paragraph:
            if pdfmetrics.stringWidth(line + ch, font, size) <= width:
                line += ch
            else:
                lines.append(line)
                line = ch
        lines.append(line)
    return lines


def draw_text(c, text, x, y, width, size=10, leading=16, font="Sans", color=None,
              max_lines=None):
    """Draw wrapped text downward from baseline y.

    Returns (last baseline used, number of lines drawn).
    """
    lines = _wrap(text, width, font, size)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color if color is not None else base.TEXT)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * leading, line)
    return y - (len(lines) - 1) * leading, len(lines)


def eyebrow(c, text, x, y):
    c.setFont("SansB", 7.5)
    c.setFillColor(base.ACCENT)
    c.drawString(x, y, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: 10 passed

- [ ] **Step 5: Port the cover and profile renderers**

`tools/build_portfolio_pdf.py:250-266`(커버)과 `268-326`(프로필)을 `render_cover(doc, content)` / `render_profile(doc, content)`로 옮긴다. 좌표와 구성은 그대로 두고 폰트·색만 위 **치환 대응표**대로 바꾼다. 세 가지만 원본과 달라진다.

1. `page_frame(c, n, section)` 대신 함수 시작에 `doc.begin_page()`, 끝에 `doc.footer('BRAND & CONTENT PORTFOLIO')`를 쓴다.
2. 커버의 인물 사진은 `asset("portrait")` 대신 사이트 사진을 쓴다:

```python
photo = base.cached_image(doc.data["site"], doc.data["photo"], 200, doc.quality)
if photo:
    draw_image_cover(doc.c, photo, 592, 98, 205, 390, radius=14)
# no photo on the site: the headline block simply keeps the full page width
```

3. 프로필의 경력·학력·수상은 `data["experience"]` 대신 스크레이핑 결과를 쓴다: `doc.data["experience"]`, `doc.data["education"]`, `doc.data["awards"]`. 각 원소의 키는 경력이 `company` / `period` / `role` / `bullets`, 학력·수상이 `main` / `period`다.

원본은 `yy = draw_text(...)`로 y만 받지만 이 모듈의 `draw_text`는 `(y, 줄 수)`를 반환한다. 이식할 때 모든 호출부를 `yy, _ = draw_text(...)`로 바꾼다. 이는 Task 5·6의 이식에도 똑같이 적용된다.

`draw_image_cover`는 `tools/build_portfolio_pdf.py:110-138`을 그대로 옮긴다 (Pillow로 비율 유지 크롭 후 `roundRect` 클리핑).

- [ ] **Step 6: Verify the two pages render**

Run:
```bash
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'tools')
import build_general_portfolio_pdf as base, showcase_pages as sp, json, io
base.ensure_fonts()
data = base.scrape('https://jgpark.up.railway.app','ko')
content = sp.load_showcase_content(json.load(io.open('data/hyundai_application_2026.json',encoding='utf-8')))
d = base.Doc('pdf/_probe.pdf', data, base.LABELS['ko'])
sp.render_cover(d, content); sp.render_profile(d, content); d.c.save()
from pypdf import PdfReader; r=PdfReader('pdf/_probe.pdf')
print('pages', len(r.pages)); print((r.pages[0].extract_text() or '')[:80])
"
```
Expected: `pages 2` 와 커버에서 추출된 헤드라인 텍스트

- [ ] **Step 7: Commit**

```bash
git add tools/showcase_pages.py tests/test_showcase_pages.py
git commit -m "feat: port cover and profile pages into showcase_pages

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: IMPACT·EXPERIENCE MAP 면

**Files:**
- Modify: `tools/showcase_pages.py`

**Interfaces:**
- Consumes: `card_grid` (Task 3), `draw_text` / `eyebrow` (Task 4)
- Produces: `render_impact(doc, content) -> None`, `render_experience_map(doc, content) -> None`

- [ ] **Step 1: Port the impact page**

`tools/build_portfolio_pdf.py:328-361`을 `render_impact(doc, content)`로 옮긴다. 숫자 타일 4개의 좌표는 하드코딩 대신 `card_grid`로 계산한다:

```python
tiles = card_grid(base.MARGIN, 470, base.PAGE_W - 2 * base.MARGIN, 145,
                  cols=4, rows=1, gap=16)
```

타일 값은 `content["portfolio_summary"]`에서 읽는다. 표시 순서와 라벨은 다음과 같다.

```python
TILES = [
    ("organic_subscribers", "국내·글로벌 채널 합산"),
    ("global_content_views", "글로벌 콘텐츠 누적 조회"),
    ("popup_commerce_revenue", "팝업 연계 커머스 매출"),
    ("export_market_viewer_share", "글로벌 시리즈 수출국 시청 비중"),
]
```

첫 타일만 값 앞에 `오가닉 구독자 ` 접두어를 붙여 원본 `오가닉 구독자 10만+` 표기를 유지한다. 하단 3단 설명은 원본 좌표를 그대로 쓴다.

- [ ] **Step 2: Port the experience map page**

`tools/build_portfolio_pdf.py:363-384`를 `render_experience_map(doc, content)`로 옮긴다. 카드 4개의 좌표는 `card_grid`로 계산한다:

```python
cells = card_grid(base.MARGIN, 73, base.PAGE_W - 2 * base.MARGIN, 379,
                  cols=2, rows=2, gap=24)
```

카드 내용은 `content["experience_map"]`의 `eyebrow` / `heading` / `body`에서 읽는다. 원본의 `map_cards` 리터럴은 쓰지 않는다.

- [ ] **Step 3: Verify both pages render**

Run:
```bash
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'tools')
import build_general_portfolio_pdf as base, showcase_pages as sp, json, io
base.ensure_fonts()
data = base.scrape('https://jgpark.up.railway.app','ko')
content = sp.load_showcase_content(json.load(io.open('data/hyundai_application_2026.json',encoding='utf-8')))
d = base.Doc('pdf/_probe.pdf', data, base.LABELS['ko'])
sp.render_impact(d, content); sp.render_experience_map(d, content); d.c.save()
from pypdf import PdfReader; r=PdfReader('pdf/_probe.pdf')
t='\n'.join(p.extract_text() or '' for p in r.pages)
print('pages', len(r.pages))
for s in ['오가닉 구독자 10만+','3.2억 원','국내 캐릭터 IP 채널','04 · PRODUCTION']:
    print('OK ' if s in t else 'MISS', s)
"
```
Expected: `pages 2` 와 네 문자열 모두 `OK`

- [ ] **Step 4: Commit**

```bash
git add tools/showcase_pages.py
git commit -m "feat: port impact and experience map pages into showcase_pages

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: PRODUCTION FOUNDATION·HOW I WORK·클로징 면

**Files:**
- Modify: `tools/showcase_pages.py`

**Interfaces:**
- Consumes: `card_grid` (Task 3), `draw_text` / `eyebrow` / `draw_image_cover` (Task 4)
- Produces:
  - `render_production_foundation(doc, content, production) -> None` — `production`은 Task 2 `split_projects`의 두 번째 반환값(프로젝트 dict 2개)
  - `render_working_method(doc, content) -> None`
  - `render_closing(doc, content) -> None`

- [ ] **Step 1: Port the production foundation page**

`tools/build_portfolio_pdf.py:427-433`과 `mini_case`(`220-248`)를 옮긴다. `mini_case`는 모듈 내부 함수 `_mini_case(doc, project, x, y, width, height)`로 만들고, 카드 2개의 좌표는 `card_grid`로 계산한다:

```python
cells = card_grid(base.MARGIN, 66, base.PAGE_W - 2 * base.MARGIN, 390,
                  cols=2, rows=1, gap=24)
```

원본 `mini_case`는 JSON 프로젝트(`title_ko`, `overview`, `results`)를 읽지만, 여기서는 스크레이핑 dict를 받으므로 필드를 이렇게 대응시킨다.

| 원본 | 대체 |
|---|---|
| `project["title_ko"]` | `project["title"]` |
| `project["overview"]` | `project["desc"]` |
| `project["results"]` (리스트) | `base.split_kpi(project["kpi"])[1]` (불릿) |
| `project["category_ko"]` | `project["category"]` |
| `project["role"]` | `project["role"]` |

이미지는 `asset(key)` 대신 첫 이미지를 쓴다:

```python
images = project.get("images") or []
photo = base.cached_image(doc.data["site"], images[0], 160, doc.quality) if images else None
```

`production`이 2개 미만이면 있는 만큼만 그린다.

- [ ] **Step 2: Port the working method page**

`tools/build_portfolio_pdf.py:435-461`을 `render_working_method(doc, content)`로 옮긴다. 카드 3개 좌표는 `card_grid(base.MARGIN, 155, base.PAGE_W - 2 * base.MARGIN, 460, cols=3, rows=1, gap=24)`로 계산하고, 내용은 `content["working_method"]`의 `step` / `label` / `body` / `evidence`에서 읽는다.

- [ ] **Step 3: Port the closing page**

`tools/build_portfolio_pdf.py:463-496`을 `render_closing(doc, content)`로 옮긴다. 연락처와 수상은 스크레이핑 결과를 쓴다: `doc.data["email"]`, `doc.data["linkedin"]`, `doc.data["site"]`, `doc.data["awards"]`.

첨부본의 장점을 하나 가져온다 — 우측 SELECTED RECOGNITION 카드 아래 여백에 사이트 QR을 넣는다:

```python
doc.qr(doc.data["site"], base.PAGE_W - base.MARGIN - 78, 96, 78)
```

- [ ] **Step 4: Verify the three pages render**

Run:
```bash
.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'tools')
import build_general_portfolio_pdf as base, showcase_pages as sp, json, io
base.ensure_fonts()
data = base.scrape('https://jgpark.up.railway.app','ko')
content = sp.load_showcase_content(json.load(io.open('data/hyundai_application_2026.json',encoding='utf-8')))
main, production, missing = sp.split_projects(data['projects'], content['production_titles'])
print('main', len(main), 'production', len(production), 'missing', missing)
d = base.Doc('pdf/_probe.pdf', data, base.LABELS['ko'])
sp.render_production_foundation(d, content, production)
sp.render_working_method(d, content)
sp.render_closing(d, content); d.c.save()
from pypdf import PdfReader; r=PdfReader('pdf/_probe.pdf')
t='\n'.join(p.extract_text() or '' for p in r.pages)
print('pages', len(r.pages))
for s in ['DEFINE','MEASURE & TOOL','junglepark94@gmail.com']:
    print('OK ' if s in t else 'MISS', s)
"
```
Expected: `main 8 production 2 missing []`, `pages 3`, 세 문자열 모두 `OK`

- [ ] **Step 5: Commit**

```bash
git add tools/showcase_pages.py
git commit -m "feat: port production, method and closing pages into showcase_pages

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `--layout showcase` 배선과 최종 PDF 생성

**Files:**
- Modify: `tools/build_general_portfolio_pdf.py:390` (`Doc.__init__`), `:978-990` (`Doc.build`), `:1000` (`render`), `:1013` (`build`), `:1033` (`__main__`)
- Modify: `tests/test_portfolio_pdf.py:17`
- Test: `tests/test_showcase_pages.py`

**Interfaces:**
- Consumes: Task 1–6의 `load_showcase_content`, `split_projects`, `render_cover`, `render_profile`, `render_impact`, `render_experience_map`, `render_production_foundation`, `render_working_method`, `render_closing`
- Produces: CLI `--layout {general,showcase}`; `render(site, lang, out, data=None, layout='general')`; `build(site, lang, out, max_mb=None, layout='general')`

- [ ] **Step 1: Write the failing test**

`tests/test_showcase_pages.py` 끝에 추가:

이 테스트는 두 레이아웃이 실제로 서로 다른 면 순서를 만드는지를 확인한다. 스크레이핑과 이미지 다운로드를 피하려고 최소 데이터를 직접 만든다.

```python
MINIMAL_SITE_DATA = {
    "name": "박종걸", "role": "브랜드 마케팅", "photo": "", "site": "http://example.test",
    "lang": "ko", "about": ["소개"], "education": [], "language": [], "awards": [],
    "experience": [], "email": "me@example.test", "linkedin": "",
    "projects": [
        {"title": f"프로젝트 {i}", "period": "2025", "desc": "설명", "detail": "",
         "kpi": "100만 | 조회수", "role": "기획", "category": "콘텐츠",
         "links": [], "images": [], "tags": ""}
        for i in range(1, 4)
    ] + [
        {"title": "산꾼도시여자들", "period": "2021", "desc": "설명", "detail": "",
         "kpi": "", "role": "조연출", "category": "제작",
         "links": [], "images": [], "tags": ""},
        {"title": "샤이니의 빛돌기획", "period": "2020", "desc": "설명", "detail": "",
         "kpi": "", "role": "조연출", "category": "제작",
         "links": [], "images": [], "tags": ""},
    ],
}


def _render(tmp_path, layout, content=None):
    import build_general_portfolio_pdf as base
    from pypdf import PdfReader

    base.ensure_fonts()
    out = tmp_path / f"{layout}.pdf"
    base.Doc(str(out), dict(MINIMAL_SITE_DATA), base.LABELS["ko"],
             layout=layout, content=content).build()
    reader = PdfReader(str(out))
    return len(reader.pages), "\n".join(p.extract_text() or "" for p in reader.pages)


def test_general_layout_keeps_cover_profile_index_projects_closing(tmp_path):
    pages, text = _render(tmp_path, "general")

    # cover + profile + index + 5 projects + closing
    assert pages == 9
    assert "산꾼도시여자들" in text


def test_showcase_layout_wraps_the_detail_projects_in_the_editorial_pages(tmp_path):
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    content = showcase_pages.load_showcase_content(data)

    pages, text = _render(tmp_path, "showcase", content)

    # cover + profile + impact + map + 3 detail projects + production + method + closing
    assert pages == 10
    assert "오가닉 구독자 10만+" in text      # impact page
    assert "04 · PRODUCTION" in text        # experience map page
    assert "MEASURE & TOOL" in text         # working method page
    assert "01 / 03" in text                # detail label counts only the 3 main projects
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'layout'`

- [ ] **Step 3: Add the layout parameter to Doc**

`tools/build_general_portfolio_pdf.py:390`의 시그니처를 바꾼다:

```python
    def __init__(self, path, data, labels, total_pages=None, quality=JPEG_QUALITY,
                 project_pages=None, layout='general', content=None):
```

`__init__` 본문 끝(`self.c.setCreator(...)` 다음)에 두 줄을 추가한다:

```python
        self.layout = layout
        self.content = content
```

- [ ] **Step 4: Branch Doc.build on the layout**

`tools/build_general_portfolio_pdf.py:978-990`의 `build`를 아래로 교체한다. `general` 경로의 동작은 한 줄도 바뀌지 않는다.

```python
    def build(self):
        global first_page
        if self.layout == 'showcase':
            return self._build_showcase()
        self.cover()
        self.profile()
        self.index_page()
        started = {}
        for i, p in enumerate(self.data['projects'], 1):
            first_page = self.page_no + 1
            started[i] = first_page
            self.project(i, p)
        self.closing()
        self.c.save()
        return self.page_no, started

    def _build_showcase(self):
        global first_page
        import showcase_pages as sp

        content = self.content
        main, production, missing = sp.split_projects(
            self.data['projects'], content['production_titles'])
        if missing:
            print('  warning: production titles not found on the site:', ', '.join(missing))
        if len(main) != 8:
            print(f'  warning: expected 8 detail projects, got {len(main)}')

        # Doc.project() labels pages "NN / total" from data['projects']
        self.data = dict(self.data, projects=main)

        sp.render_cover(self, content)
        sp.render_profile(self, content)
        sp.render_impact(self, content)
        sp.render_experience_map(self, content)
        started = {}
        for i, p in enumerate(main, 1):
            first_page = self.page_no + 1
            started[i] = first_page
            self.project(i, p)
        sp.render_production_foundation(self, content, production)
        sp.render_working_method(self, content)
        sp.render_closing(self, content)
        self.c.save()
        return self.page_no, started
```

- [ ] **Step 5: Thread layout through render() and build()**

`render`(`:1000`)와 `build`(`:1013`)를 아래로 교체한다.

```python
def render(site, lang, out, data=None, layout='general', content=None):
    ensure_fonts()
    if data is None:
        data = scrape(site, lang)
    labels = LABELS[lang]
    # two passes so the footer can show "page / total"
    tmp = out + '.tmp'
    total, pages = Doc(tmp, data, labels, quality=JPEG_QUALITY,
                       layout=layout, content=content).build()
    Doc(out, data, labels, total_pages=total, quality=JPEG_QUALITY,
        project_pages=pages, layout=layout, content=content).build()
    os.remove(tmp)
    return total


def build(site, lang, out, max_mb=None, layout='general'):
    global RENDER_DPI, JPEG_QUALITY
    ensure_fonts()
    content = None
    if layout == 'showcase':
        import json as _json
        import showcase_pages as sp
        path = os.path.join(ROOT, 'data', 'hyundai_application_2026.json')
        with open(path, encoding='utf-8') as fh:
            content = sp.load_showcase_content(_json.load(fh))
    print('scraping', site, lang)
    data = scrape(site, lang)
    print(f"  {data['name']} · {len(data['projects'])} projects · {len(data['experience'])} jobs")
    steps = SIZE_STEPS if max_mb else [(RENDER_DPI, JPEG_QUALITY)]
    for dpi, quality in steps:
        RENDER_DPI, JPEG_QUALITY = dpi, quality
        total = render(site, lang, out, data, layout=layout, content=content)
        size_mb = os.path.getsize(out) / 1024 / 1024
        note = f'{total} pages, {size_mb:.2f} MB, {dpi} dpi'
        if not max_mb or size_mb <= max_mb:
            print('wrote', out, f'({note})')
            return out
        print(f'  {note} — over {max_mb} MB, retrying smaller')
    print('wrote', out, f'({total} pages, {size_mb:.2f} MB — could not reach {max_mb} MB)')
    return out
```

- [ ] **Step 6: Add the CLI flag**

`__main__` 블록(`:1033` 부근)에 인자를 추가하고 `build` 호출에 넘긴다.

```python
    ap.add_argument('--layout', choices=['general', 'showcase'], default='general',
                    help="'showcase' combines the editorial intro/closing pages "
                         "with the project detail pages")
```

`build(...)` 호출을 다음으로 바꾼다:

```python
        build(args.url.rstrip('/'), args.lang, out, max_mb=args.max_mb, layout=args.layout)
```

기본 출력 파일명이 레이아웃에 따라 갈리도록 `out` 계산도 바꾼다:

```python
    out = args.out or os.path.join(PDF_DIR, f"portfolio_{args.layout}_{args.lang}{suffix}.pdf")
```

사이트 접근 실패는 기존 `__main__`의 `except urllib.error.URLError` 가드가 그대로 처리한다 (`sys.exit('network error: ...')`). 새로 추가할 것은 없다.

- [ ] **Step 7: Run the unit tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_showcase_pages.py tests/test_portfolio_pdf_tool.py -v`
Expected: 14 passed

- [ ] **Step 8: Confirm the general layout is unchanged**

Run:
```bash
.venv/Scripts/python.exe tools/build_general_portfolio_pdf.py --out pdf/_general_check.pdf
.venv/Scripts/python.exe -c "
from pypdf import PdfReader
print('pages', len(PdfReader('pdf/_general_check.pdf').pages))
"
```
Expected: `pages 13`

- [ ] **Step 9: Generate the showcase PDF**

Run:
```bash
.venv/Scripts/python.exe tools/build_general_portfolio_pdf.py --layout showcase --max-mb 2 --out "C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/박종걸_포트폴리오_2026.pdf"
```
Expected: 마지막 줄이 `wrote ... (15 pages, N.NN MB, 200 dpi)`. 경고 줄이 없어야 한다.

- [ ] **Step 10: Widen the page-count assertion**

`tests/test_portfolio_pdf.py:17`을 바꾼다.

```python
    assert 15 <= len(reader.pages) <= 18
```

- [ ] **Step 11: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: 모두 통과, 실패 0

- [ ] **Step 12: Commit**

```bash
git add tools/build_general_portfolio_pdf.py tools/showcase_pages.py tests/test_showcase_pages.py tests/test_portfolio_pdf.py
git commit -m "feat: add --layout showcase combining editorial and detail pages

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 13: Clean up probe files**

```bash
rm -f pdf/_probe.pdf pdf/_general_check.pdf tests/_scratch.pdf
```

`pdf/`는 `.gitignore` 대상이라 커밋에 영향이 없다. `tests/_scratch.pdf`가 추적되지 않는지 `git status`로 확인한다.
