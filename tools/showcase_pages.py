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
        yy, _ = draw_text(c, "\n".join(exp["bullets"]), base.MARGIN + 18, yy - 3,
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
        last_edu_yy, _ = draw_text(c, f"{edu['main']}\n{edu['period']}", mid_x + 18, yy,
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
