# -*- coding: utf-8 -*-
"""Static page renderers for the `showcase` portfolio PDF layout.

The project detail pages come from build_general_portfolio_pdf.Doc.project and are
not touched here. This module only draws the seven hand-laid-out pages around them:
cover, profile, impact, experience map, production foundation, working method, closing.

Editorial copy lives in data/hyundai_application_2026.json, not in this file.
"""

import io
import re
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

import build_general_portfolio_pdf as base

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
    """Accent-outlined pill label, as in build_portfolio_pdf.eyebrow (151-158)."""
    w = pdfmetrics.stringWidth(text, "SansB", 8) + 18
    c.setStrokeColor(base.ACCENT)
    c.setLineWidth(0.8)
    c.roundRect(x, y - 5, w, 19, 9, fill=0, stroke=1)
    c.setFont("SansB", 8)
    c.setFillColor(base.ACCENT)
    c.drawString(x + 9, y, text)


def title(c, text, x=base.MARGIN, y=base.PAGE_H - 72, size=26,
          width=base.PAGE_W - base.MARGIN * 2):
    """Ported from build_portfolio_pdf.title (161-177).

    Font follows the size-based substitution rule: >=17 -> SerifXB,
    13-17 -> SerifB, otherwise SansB.
    """
    if size >= 17:
        font = "SerifXB"
    elif size >= 13:
        font = "SerifB"
    else:
        font = "SansB"
    y, _ = draw_text(c, text, x, y, width, size=size, leading=size * 1.35,
                      font=font, color=base.TEXT)
    return y


def draw_image_cover(c, image_path, x, y, width, height, radius=8):
    """Ported from build_portfolio_pdf.draw_image_cover (110-138)."""
    if not image_path or not Path(image_path).exists():
        c.setFillColor(base.BG_ALT)
        c.roundRect(x, y, width, height, radius, fill=1, stroke=0)
        return
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        source_ratio = image.width / image.height
        target_ratio = width / height
        if source_ratio > target_ratio:
            crop_width = int(image.height * target_ratio)
            left = (image.width - crop_width) // 2
            image = image.crop((left, 0, left + crop_width, image.height))
        else:
            crop_height = int(image.width / target_ratio)
            top = (image.height - crop_height) // 2
            image = image.crop((0, top, image.width, top + crop_height))
        image.thumbnail((int(width * 2.2), int(height * 2.2)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        buffer.seek(0)
        c.saveState()
        path = c.beginPath()
        path.roundRect(x, y, width, height, radius)
        c.clipPath(path, stroke=0, fill=0)
        c.drawImage(ImageReader(buffer), x, y, width, height, mask="auto")
        c.restoreState()


def render_cover(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '01 Cover' block (250-266)."""
    c = doc.c
    doc.begin_page()
    c.setFillColor(base.ACCENT)
    c.rect(0, 0, 16, base.PAGE_H, fill=1, stroke=0)
    c.setFont("SansB", 8)
    c.setFillColor(base.ACCENT)
    c.drawString(base.MARGIN, base.PAGE_H - 57, "BRAND MARKETING · CONTENT STRATEGY · 2026")
    draw_text(c, "콘텐츠로 팬덤을 만들고,\n공간과 상품으로\n브랜드 경험을 확장합니다.",
              base.MARGIN, base.PAGE_H - 125, 500, size=30, leading=44, font="SerifXB")
    draw_text(c, "PD의 제작 감각과 마케터의 성과 감각을 함께 갖춘\n브랜드 마케팅·콘텐츠 전략가",
              base.MARGIN, 208, 455, size=11, leading=19, color=base.MUTED)
    c.setFont("SerifXB", 17)
    c.setFillColor(base.TEXT)
    c.drawString(base.MARGIN, 142, "박종걸")
    c.setFont("Sans", 10)
    c.setFillColor(base.MUTED)
    c.drawString(base.MARGIN, 122, "Jonggeol Park")

    photo = base.cached_image(doc.data["site"], doc.data["photo"], 200, doc.quality)
    if photo:
        draw_image_cover(doc.c, photo, 592, 98, 205, 390, radius=14)
    # no photo on the site: the headline block simply keeps the full page width

    doc.footer("BRAND & CONTENT PORTFOLIO")


def render_profile(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '02 Profile' block (268-326)."""
    c = doc.c
    doc.begin_page()
    eyebrow(c, "PROFILE", base.MARGIN, base.PAGE_H - 58)
    title(c, "콘텐츠를 만들던 사람이, 브랜드를 키우는 사람이 되었습니다",
          y=base.PAGE_H - 98, size=22)
    draw_text(
        c,
        "CJ ENM 제작 PD로 시작해 빙그레 콘텐츠전략팀에서 국내 캐릭터 IP, 글로벌 브랜디드 콘텐츠, "
        "오프라인 브랜드 경험을 담당했습니다. 고객이 머무는 이유를 콘텐츠로 만들고, 그 관계를 공간과 "
        "상품으로 확장해 측정 가능한 성과로 연결합니다.",
        base.MARGIN, 438, 752, size=9.7, leading=17)

    col_w, gap, base_y, box_h = 240, 16, 63, 318

    # EXPERIENCE
    c.setFillColor(base.BG_ALT)
    c.roundRect(base.MARGIN, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("SansB", 9)
    c.setFillColor(base.ACCENT)
    c.drawString(base.MARGIN + 18, base_y + box_h - 28, "EXPERIENCE")
    yy = base_y + box_h - 60
    for exp in doc.data["experience"]:
        c.setFont("SansB", 12)
        c.setFillColor(base.TEXT)
        c.drawString(base.MARGIN + 18, yy, exp["company"])
        c.setFont("Sans", 8.5)
        c.setFillColor(base.MUTED)
        c.drawRightString(base.MARGIN + col_w - 18, yy, exp["period"].replace("–", "-"))
        yy, _ = draw_text(c, exp["role"], base.MARGIN + 18, yy - 20, col_w - 36,
                           size=8.5, leading=13, font="SansB")
        yy, _ = draw_text(c, " · ".join(exp["bullets"]), base.MARGIN + 18, yy - 17,
                           col_w - 36, size=7.7, leading=12.5, color=base.MUTED, max_lines=4)
        yy -= 18

    # EDUCATION & LANGUAGE
    mid_x = base.MARGIN + col_w + gap
    c.setFillColor(base.SURFACE)
    c.roundRect(mid_x, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("SansB", 9)
    c.setFillColor(base.ACCENT)
    c.drawString(mid_x + 18, base_y + box_h - 28, "EDUCATION & LANGUAGE")

    # Education and language entries come from the live site scrape (currently
    # 2 and 3 items, versus the single entry each the original layout assumed),
    # so this block's height varies run to run. The separators below are
    # anchored to the actual last baseline drawn (via draw_text's return value)
    # rather than the fixed offsets the original used, with gaps (23/26/40/26)
    # matching the visual spacing build_portfolio_pdf.py:268-326 used for its
    # single-entry case.
    yy = base_y + box_h - 62
    last_edu_yy = yy
    for edu in doc.data["education"]:
        last_edu_yy, _ = draw_text(c, f"{edu['main']} {edu['sub']}\n{edu['period']}", mid_x + 18, yy,
                                    col_w - 36, size=9, leading=15, font="SansB")
        yy = last_edu_yy - 15
    sep1_y = last_edu_yy - 23
    c.setStrokeColor(base.BORDER)
    c.line(mid_x + 18, sep1_y, mid_x + col_w - 18, sep1_y)

    yy = sep1_y - 26
    last_lang_yy = yy
    for lang in doc.data["language"]:
        last_lang_yy, _ = draw_text(c, f"{lang['main']} {lang['sub']}".strip(), mid_x + 18, yy,
                                     col_w - 36, size=9, leading=20)
        yy = last_lang_yy - 20
    sep2_y = last_lang_yy - 40
    c.setStrokeColor(base.BORDER)
    c.line(mid_x + 18, sep2_y, mid_x + col_w - 18, sep2_y)
    draw_text(c, "Premiere Pro · Photoshop\n데이터 분석 · AI 도구 활용", mid_x + 18,
              sep2_y - 26, col_w - 36, size=8.7, leading=18)

    # CORE CAPABILITIES
    right_x = mid_x + col_w + gap
    c.setFillColor(base.BG_ALT)
    c.roundRect(right_x, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("SansB", 9)
    c.setFillColor(base.ACCENT)
    c.drawString(right_x + 18, base_y + box_h - 28, "CORE CAPABILITIES")
    capabilities = [
        ("01", "콘텐츠 전략·제작", "예능 PD 기반 포맷 설계와 제작 품질 관리"),
        ("02", "브랜드 경험", "세계관을 공간·상품·커머스로 확장"),
        ("03", "글로벌 마케팅", "현지 문화와 알고리즘에 맞춘 운영"),
        ("04", "데이터·AI 활용", "성과 분석과 반복 업무 도구화"),
    ]
    yy = base_y + box_h - 65
    for num, name, desc in capabilities:
        c.setFont("SerifB", 15)
        c.setFillColor(base.ACCENT)
        c.drawString(right_x + 18, yy, num)
        c.setFont("SansB", 11)
        c.setFillColor(base.TEXT)
        c.drawString(right_x + 58, yy + 1, name)
        draw_text(c, desc, right_x + 58, yy - 17, col_w - 76, size=7.8, leading=12.5,
                  color=base.MUTED)
        yy -= 66

    doc.footer("BRAND & CONTENT PORTFOLIO")


def render_impact(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '03 Impact' block (328-361)."""
    c = doc.c
    doc.begin_page()
    summary = content["portfolio_summary"]
    eyebrow(c, "IMPACT AT A GLANCE", base.MARGIN, base.PAGE_H - 58)
    title_y = title(c, "서로 다른 채널에서 관계를 만들고, 브랜드 경험으로 확장했습니다",
                     y=base.PAGE_H - 100, size=23)

    # The brief's literal tiles = card_grid(base.MARGIN, 470, ..., 145, ...) puts
    # the grid's top edge at 470 + 145 = 615pt, above PAGE_H (~595pt) and
    # colliding with the title above it. Anchor the grid below the title's
    # actual last baseline instead, keeping the same 145pt tile height and
    # landing close to the original box's top edge (454pt).
    tiles_top = title_y - 34
    tiles = card_grid(base.MARGIN, tiles_top - 145, base.PAGE_W - 2 * base.MARGIN, 145,
                       cols=4, rows=1, gap=16)
    TILES = [
        ("organic_subscribers", "국내·글로벌 채널 합산"),
        ("global_content_views", "글로벌 콘텐츠 누적 조회"),
        ("popup_commerce_revenue", "팝업 연계 커머스 매출"),
        ("export_market_viewer_share", "글로벌 시리즈 수출국 시청 비중"),
    ]
    for i, ((key, label), (x, y, w, h)) in enumerate(zip(TILES, tiles)):
        value = summary[key]
        if i == 0:
            value = f"오가닉 구독자 {value}"
        c.setFillColor(base.SURFACE)
        c.roundRect(x, y, w, h, 10, fill=1, stroke=0)
        c.setFont("SansB", 16 if i == 0 else 22)
        c.setFillColor(base.ACCENT)
        c.drawString(x + 18, y + h - 42, value)
        draw_text(c, label, x + 18, y + h - 69, w - 36, size=8.5, leading=13,
                  color=base.MUTED)

    columns = [
        ("국내 캐릭터 IP 채널", "빙그레우스를 버추얼 유튜버로 전환해 검색·순 시청자·재방문·재생률을 함께 성장시키고 팬덤 기반을 만들었습니다."),
        ("글로벌 수출 브랜드 채널", "국가별 문화 코드와 현지 알고리즘에 맞는 시리즈를 설계해 제품 인지도와 오가닉 구독자를 함께 확보했습니다."),
        ("온라인 → 오프라인", "온라인 세계관을 공간·굿즈·커머스로 확장하고, 현장의 콘텐츠가 다시 SNS로 돌아오는 순환을 설계했습니다."),
    ]
    for i, (head, body) in enumerate(columns):
        x = base.MARGIN + i * 255
        c.setFont("SansB", 13)
        c.setFillColor(base.TEXT)
        c.drawString(x, 290, head)
        c.setStrokeColor(base.ACCENT)
        c.setLineWidth(2)
        c.line(x, 275, x + 44, 275)
        draw_text(c, body, x, 250, 218, size=9.2, leading=16)

    doc.footer("BRAND & CONTENT PORTFOLIO")


def render_experience_map(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '04 Experience map' block (363-384)."""
    c = doc.c
    doc.begin_page()
    eyebrow(c, "EXPERIENCE MAP", base.MARGIN, base.PAGE_H - 58)
    title(c, "채널의 목적과 고객에 따라 다른 성장 공식을 설계했습니다",
          y=base.PAGE_H - 96, size=22)

    cells = card_grid(base.MARGIN, 73, base.PAGE_W - 2 * base.MARGIN, 379,
                       cols=2, rows=2, gap=24)
    for card, (x, y, w, h) in zip(content["experience_map"], cells):
        c.setFillColor(base.SURFACE)
        c.roundRect(x, y, w, h, 11, fill=1, stroke=0)
        c.setFont("SansB", 7.5)
        c.setFillColor(base.ACCENT)
        c.drawString(x + 18, y + h - 31, card["eyebrow"])
        c.setFont("SansB", 13)
        c.setFillColor(base.TEXT)
        c.drawString(x + 18, y + h - 62, card["heading"])
        draw_text(c, card["body"], x + 18, y + h - 91, w - 36, size=8.7, leading=16,
                  color=base.MUTED)

    doc.footer("BRAND & CONTENT PORTFOLIO")


def _mini_case(doc, project, x, y, width, height):
    """Ported from build_portfolio_pdf.mini_case (220-236).

    The original reads a JSON project (title_ko/overview/results/category_ko);
    this receives a scraped project dict instead, per the field mapping in
    task-6-brief.md:
      title_ko -> title, overview -> desc, results -> split_kpi(kpi)[1] bullets,
      category_ko -> category, role -> role. The image comes from the first
      scraped image (there is no asset(key) lookup here).
    """
    c = doc.c
    c.setFillColor(base.SURFACE)
    c.roundRect(x, y, width, height, 10, fill=1, stroke=0)

    images = project.get("images") or []
    # 400 is render resolution for the card's image box, not the drawn size
    photo = base.cached_image(doc.data["site"], images[0], 400, doc.quality) if images else None
    draw_image_cover(c, photo, x, y + height - 122, width, 122, radius=10)

    c.setFont("SansB", 12)
    c.setFillColor(base.TEXT)
    title_y, _ = draw_text(c, project["title"], x + 16, y + height - 145, width - 32,
                            size=11.5, leading=16, font="SansB", max_lines=2)

    c.setFont("Sans", 7.5)
    c.setFillColor(base.MUTED)
    role_y = title_y - 22
    role_y, _ = draw_text(c, project.get("role") or "", x + 16, role_y, width - 32,
                           size=7.5, leading=13, font="Sans", color=base.MUTED, max_lines=1)

    desc_y, _ = draw_text(c, project.get("desc") or "", x + 16, role_y - 22, width - 32,
                           size=8.1, leading=13, color=base.MUTED, max_lines=4)

    _, bullets = base.split_kpi(project.get("kpi"))
    yy = desc_y - 24
    for item in bullets[:3]:
        c.setFillColor(base.ACCENT)
        c.circle(x + 18, yy + 2, 1.8, fill=1, stroke=0)
        draw_text(c, item, x + 27, yy, width - 42, size=8, leading=12, max_lines=1)
        yy -= 17


def render_production_foundation(doc, content, production):
    """Ported from build_portfolio_pdf.build_pdf, the '13 Production foundation'
    block (427-433), plus its mini_case helper (220-248)."""
    c = doc.c
    doc.begin_page()
    eyebrow(c, "PRODUCTION FOUNDATION", base.MARGIN, base.PAGE_H - 58)
    title(c, "사람과 이야기를 끝까지 완성하는 제작 현장에서 시작했습니다",
          y=base.PAGE_H - 96, size=22)

    cells = card_grid(base.MARGIN, 66, base.PAGE_W - 2 * base.MARGIN, 390,
                       cols=2, rows=1, gap=24)
    for project, (x, y, w, h) in zip(production, cells):
        _mini_case(doc, project, x, y, w, h)

    doc.footer("BRAND & CONTENT PORTFOLIO")


def render_working_method(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '14 How I work' block
    (435-461)."""
    c = doc.c
    doc.begin_page()
    eyebrow(c, "WORKING METHOD", base.MARGIN, base.PAGE_H - 58)
    title(c, "감각으로 시작하되, 고객 행동과 데이터로 끝까지 검증합니다",
          y=base.PAGE_H - 96, size=22)

    # The brief's literal card_grid(..., 155, ..., 460, ...) puts the grid's
    # top edge at 155 + 460 = 615pt, above PAGE_H (~595pt) — the cards then
    # overflow the page and their opaque fill paints over the eyebrow/title
    # above them. The original build_portfolio_pdf.py used a 330pt-tall card
    # starting at y=118 for this row (435-461); reuse those figures, which
    # also happen to match this port's top-anchored offsets below exactly
    # (h-48/h-82/h-123 with h=330 reproduce the original's absolute y
    # positions of 282/248/207 measured from the card's y=118 origin).
    cells = card_grid(base.MARGIN, 118, base.PAGE_W - 2 * base.MARGIN, 330,
                       cols=3, rows=1, gap=24)
    for pillar, (x, y, w, h) in zip(content["working_method"], cells):
        c.setFillColor(base.SURFACE)
        c.roundRect(x, y, w, h, 12, fill=1, stroke=0)
        c.setFont("SerifXB", 26)
        c.setFillColor(base.ACCENT)
        c.drawString(x + 18, y + h - 48, pillar["step"])
        c.setFont("SansB", 9)
        c.setFillColor(base.ACCENT)
        c.drawString(x + 18, y + h - 82, pillar["label"])
        draw_text(c, pillar["body"], x + 18, y + h - 123, w - 36, size=10, leading=18,
                  font="SansB")
        line_y = y + 97
        c.setStrokeColor(base.BORDER)
        c.line(x + 18, line_y, x + w - 18, line_y)
        c.setFont("SansB", 8)
        c.setFillColor(base.MUTED)
        c.drawString(x + 18, line_y - 22, "EVIDENCE")
        draw_text(c, pillar["evidence"], x + 18, line_y - 44, w - 36, size=8.5,
                  leading=15, color=base.MUTED)

    doc.footer("BRAND & CONTENT PORTFOLIO")


def render_closing(doc, content):
    """Ported from build_portfolio_pdf.build_pdf, the '15 Closing' block
    (463-496). Contact and awards come from the scraped site data
    (doc.data["email"], doc.data["linkedin"], doc.data["site"],
    doc.data["awards"]) instead of the original static JSON contact/awards
    blocks. Awards items carry period/main/sub (from _list_items), which map
    to the original's year/title/organization. A site QR code is added under
    the recognition card, per the brief."""
    c = doc.c
    doc.begin_page()
    c.setFont("SansB", 8)
    c.setFillColor(base.ACCENT)
    c.drawString(base.MARGIN, base.PAGE_H - 58, "THANK YOU · 2026")
    draw_text(c, "콘텐츠에서 공간으로,\n공간에서 다시 콘텐츠로.",
              base.MARGIN, base.PAGE_H - 125, 520, size=31, leading=45, font="SerifXB")
    draw_text(c, "사람이 머물고, 참여하고, 다시 찾는 브랜드 경험을 설계합니다.",
              base.MARGIN, 320, 530, size=13, leading=20, color=base.MUTED)
    c.setFont("SerifXB", 18)
    c.setFillColor(base.TEXT)
    c.drawString(base.MARGIN, 230, "박종걸 · Jonggeol Park")

    # Strip scheme and www prefix from LinkedIn URL
    linkedin = doc.data["linkedin"]
    linkedin = re.sub(r'^https?://', '', linkedin)
    linkedin = re.sub(r'^www\.', '', linkedin)
    contacts = [
        ("EMAIL", doc.data["email"]),
        ("PORTFOLIO", doc.data["site"].replace("https://", "")),
        ("LINKEDIN", linkedin),
    ]
    yy = 187
    for label, value in contacts:
        c.setFont("SansB", 7.5)
        c.setFillColor(base.ACCENT)
        c.drawString(base.MARGIN, yy, label)
        c.setFont("Sans", 9)
        c.setFillColor(base.TEXT)
        c.drawString(base.MARGIN + 78, yy, value)
        yy -= 28
    c.linkURL(doc.data["site"], (base.MARGIN + 78, 145, base.MARGIN + 400, 164), relative=0)

    c.setFillColor(base.SURFACE)
    c.roundRect(548, 112, 249, 330, 12, fill=1, stroke=0)
    c.setFont("SansB", 8)
    c.setFillColor(base.ACCENT)
    c.drawString(568, 408, "SELECTED RECOGNITION")
    # The original's draw_text returns the baseline *after* the last line
    # (y - n*leading); this port's draw_text (line 107) returns the last
    # baseline actually drawn (y - (n-1)*leading), one leading short. Porting
    # the original's tight "yy - 2" / "- 20" offsets verbatim collapsed
    # multi-line award titles into their own subtitle line. Add back each
    # text's own leading before starting the next block instead.
    yy = 374
    # Sort awards by year (most recent first), being defensive about parsing
    def extract_year(award):
        match = re.search(r'\d{4}', award.get("period", ""))
        return int(match.group()) if match else 0
    sorted_awards = sorted(doc.data["awards"], key=extract_year, reverse=True)
    # Boundary: card y origin (112) + inner padding (top padding = 442 - 408 = 34)
    boundary = 146
    for award in sorted_awards:
        # Predict where this award would end to check for overflow
        title_lines = len(_wrap(award["main"], 155, "SansB", 9))
        sub_lines = len(_wrap(award["sub"], 155, "Sans", 7.5))
        main_y_pred = yy - (title_lines - 1) * 14
        sub_y_pred = (main_y_pred - 14) - (sub_lines - 1) * 12

        # Break before drawing an award whose block would cross the boundary
        if sub_y_pred < boundary:
            break

        c.setFont("SerifB", 13)
        c.setFillColor(base.ACCENT)
        c.drawString(568, yy, award["period"])
        main_y, _ = draw_text(c, award["main"], 620, yy, 155, size=9, leading=14,
                               font="SansB")
        sub_y, _ = draw_text(c, award["sub"], 620, main_y - 14, 155, size=7.5,
                              leading=12, color=base.MUTED)
        yy = sub_y - 30

    # The brief's literal doc.qr(..., PAGE_W - MARGIN - 78, 96, 78) draws a
    # 78pt QR (plus its own 6pt quiet-zone padding on every side) reaching
    # from y=90 to y=180 -- 68pt into the recognition card above it, which
    # sits at y=112. Shrink and drop the QR so its padded box (y-6 to
    # y+size+6) clears the card's bottom edge (112) with a couple points to
    # spare, while staying above the footer rule at y=32, and center it
    # under the card horizontally instead of right-aligning it off the card.
    qr_size = 60
    qr_x = 548 + (249 - qr_size) / 2
    doc.qr(doc.data["site"], qr_x, 44, qr_size)

    doc.footer("BRAND & CONTENT PORTFOLIO")
