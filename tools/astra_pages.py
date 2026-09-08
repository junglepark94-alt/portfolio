# -*- coding: utf-8 -*-
"""Page renderers for the `astra` portfolio PDF layout.

An editorial layout: a dark cover, a profile page, an overview with a clickable
table of contents, one claim-headline page per project, a production page, a
dark "how I work" page and a dark EOD/contact page.

Copy comes from data/astra_portfolio.json. Images, links, experience, education
and awards come from the scraped site. Every image is drawn with a crop-to-fill
box (never letterboxed), so mixed source aspect ratios do not leave bars.
"""
import io
import os
import re
import urllib.request
from datetime import date
from pathlib import Path

import qrcode
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

import build_general_portfolio_pdf as base


# ── Palette (sampled from the reference render) ───────────────────────
LIGHT_BG = HexColor("#f7f5ef")
DARK_BG = HexColor("#252722")
TEXT = HexColor("#252722")
TEXT_L = HexColor("#f7f5ef")           # text on dark pages
MUTED = HexColor("#5f625b")
MUTED_L = HexColor("#c6c8c1")
ACCENT = HexColor("#c44f2f")           # on light pages
ACCENT_L = HexColor("#f08964")         # on dark pages
RULE = HexColor("#dedbd2")
RULE_L = HexColor("#3e403b")
CHIP = HexColor("#eceee7")

W, H, M = base.PAGE_W, base.PAGE_H, 40
RIGHT = W - M                          # 802
COL2 = 430                             # right column x on two-column pages
COL_W = RIGHT - COL2                   # 372

REQUIRED_KEYS = ("cover", "profile", "overview", "projects", "production", "method", "eod")


def load_astra_content(data):
    """Validate the parsed astra_portfolio.json; KeyError names the first missing key."""
    for key in REQUIRED_KEYS:
        if key not in data:
            raise KeyError(key)
    return data


# ── Text and image primitives ─────────────────────────────────────────
# Moved here when the older showcase layout was retired; this module is the
# only consumer.

def _norm(title):
    return re.sub(r"\s+", " ", (title or "")).strip()


# A number keeps its digits, thousands separators and decimal point together, so
# a line never breaks inside one — "2,400만" must not wrap to "2," / "400만".
_ATOM = re.compile(r"\d[\d,.]*\d|\d|.", re.S)


def _wrap(text, width, font, size):
    """Break text to `width`, one CJK character at a time but never inside a number."""
    lines = []
    for paragraph in (text or "").split("\n"):
        line = ""
        for atom in _ATOM.findall(paragraph):
            if pdfmetrics.stringWidth(line + atom, font, size) <= width:
                line += atom
            elif line:
                lines.append(line)
                line = atom
            else:                      # a single atom wider than the box
                lines.append(atom)
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


def draw_image_cover(c, image_path, x, y, width, height, radius=8, focus_y=0.5):
    """Draw an image filling the box exactly.

    Crops the source to fill the box (never letterboxes). `focus_y` picks where a
    vertical crop is taken from: 0.5 keeps the middle, smaller values keep more
    of the top — useful for portrait screenshots whose picture sits above a caption.
    """
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
            top = int((image.height - crop_height) * focus_y)
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


# ── Small drawing helpers ─────────────────────────────────────────────

def _t(c, s, x, y, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, s)


def _rt(c, s, x, y, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawRightString(x, y, s)


def _rule(c, x1, x2, y, color, width=0.6):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, y, x2, y)


def _link_out(c, url, x, y, w, h):
    if url:
        c.linkURL(url, (x, y, x + w, y + h), relative=0, thickness=0)


def _link_in(c, key, x, y, w, h):
    c.linkRect("", key, (x, y, x + w, y + h), relative=1, thickness=0)


def _arrow_link(c, label, x, y, url=None, dest=None, font="SansB", size=7, color=ACCENT):
    """`label  >` in accent; returns the x where the next link may start."""
    s = f"{label}  >"
    _t(c, s, x, y, font, size, color)
    w = pdfmetrics.stringWidth(s, font, size)
    if url:
        _link_out(c, url, x, y - 3, w, size + 5)
    elif dest:
        _link_in(c, dest, x, y - 3, w, size + 5)
    return x + w + 26


def _qr(c, url, x, y, size, fg=DARK_BG, bg=TEXT_L):
    q = qrcode.QRCode(border=0)
    q.add_data(url)
    q.make(fit=True)
    m = q.get_matrix()
    cell = size / len(m)
    c.setFillColor(bg)
    c.rect(x - 6, y - 6, size + 12, size + 12, stroke=0, fill=1)
    c.setFillColor(fg)
    for r, row in enumerate(m):
        for col, on in enumerate(row):
            if on:
                c.rect(x + col * cell, y + size - (r + 1) * cell, cell, cell, stroke=0, fill=1)
    _link_out(c, url, x - 6, y - 6, size + 12, size + 12)


# ── Page chrome ───────────────────────────────────────────────────────

def _chrome(doc, label, dark=False):
    """Running header + footer. Page count uses the two-pass total when known."""
    c = doc.c
    fg, mu, ru = (TEXT_L, MUTED_L, RULE_L) if dark else (TEXT, MUTED, RULE)
    _t(c, "JONGGEOL PARK", M, H - 34, "SansB", 7, fg)
    _t(c, label, 240, H - 34, "Sans", 7, mu)
    _rule(c, M, RIGHT, H - 47, ru)
    _rule(c, M, RIGHT, 31, ru)
    _t(c, "BRAND MARKETING / CONTENT STRATEGY", M, 18, "Sans", 6.6, mu)
    _t(c, f"{date.today():%Y.%m}  /  PORTFOLIO", 600, 18, "Sans", 6.6, mu)
    total = f"{doc.total:02d}" if doc.total else "--"
    _rt(c, f"{doc.page_no:02d} / {total}", RIGHT, 18, "SansB", 7, fg)


def _page(doc, key, label, dark=False):
    doc.begin_page(bg=DARK_BG if dark else LIGHT_BG)
    doc.c.bookmarkPage(key)
    _chrome(doc, label, dark)


# ── Site lookups ──────────────────────────────────────────────────────

def _site_project(doc, title):
    wanted = _norm(title)
    for p in doc.data.get("projects") or []:
        if _norm(p.get("title")) == wanted:
            return p
    return None


def _image(doc, project, index, width_pt=560):
    images = (project or {}).get("images") or []
    if index >= len(images):
        return None
    return base.cached_image(doc.data["site"], images[index], width_pt, doc.quality)


def cached_youtube_thumb(video_id, width_pt, quality):
    """Thumbnail of one of the user's own videos, cached like site images.

    Shorts expose a clean vertical frame (`oar2`); regular videos only a 16:9
    `maxresdefault`. `hqdefault` is the last resort — it is 4:3 with black bars,
    so its 16:9 middle is kept. Returns None when nothing could be fetched.
    """
    os.makedirs(base.ORIG_DIR, exist_ok=True)
    os.makedirs(base.CACHE_DIR, exist_ok=True)
    src = os.path.join(base.ORIG_DIR, f"ytv_{video_id}.jpg")
    if not os.path.exists(src) or os.path.getsize(src) < 500:
        for name in ("oar2", "maxresdefault", "hqdefault"):
            try:
                data = urllib.request.urlopen(
                    f"https://i.ytimg.com/vi/{video_id}/{name}.jpg", timeout=20).read()
            except Exception:
                continue
            if len(data) < 500:
                continue
            with open(src, "wb") as fh:
                fh.write(data)
            if name == "hqdefault":
                with Image.open(src) as im:
                    w, h = im.size
                    im.convert("RGB").crop((0, int(h * 0.125), w, int(h * 0.875))).save(src, "JPEG", quality=92)
            break
        else:
            print(f"  youtube thumbnail skipped {video_id}")
            return None
    px = max(240, int(round(width_pt / 72.0 * base.RENDER_DPI)))
    target = os.path.join(base.CACHE_DIR, f"ytv_{video_id}_{px}_{quality}.jpg")
    if not os.path.exists(target):
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > px:
                im = im.resize((px, max(1, round(im.height * px / im.width))), Image.LANCZOS)
            im.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
    return target


def cached_local_tile(name, width_pt, quality):
    """Resized copy of a curated still committed under data/astra_tiles."""
    src = os.path.join(base.ROOT, "data", "astra_tiles", name)
    if not os.path.exists(src):
        print(f"  tile missing: {name}")
        return None
    px = max(240, int(round(width_pt / 72.0 * base.RENDER_DPI)))
    os.makedirs(base.CACHE_DIR, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    target = os.path.join(base.CACHE_DIR, f"tile_{stem}_{px}_{quality}.jpg")
    if not os.path.exists(target):
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > px:
                im = im.resize((px, max(1, round(im.height * px / im.width))), Image.LANCZOS)
            im.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
    return target


def _aspect(path):
    try:
        with Image.open(path) as im:
            return im.width / im.height
    except Exception:
        return 16 / 9


def _link_urls(project, labels):
    """URLs for the requested link labels, in order; falls back to the site's first links."""
    site = (project or {}).get("links") or []
    out = []
    for label in labels:
        want = _norm(label)
        hit = next((l for l in site if _norm(l.get("label")) == want), None)
        hit = hit or next((l for l in site if _norm(l.get("label")).startswith(want)), None)
        out.append((label, hit["url"] if hit else None))
    return out


# ── Pages ─────────────────────────────────────────────────────────────

def render_cover(doc, content):
    c, cv = doc.c, content["cover"]
    _page(doc, "page-cover", "PORTFOLIO 2026", dark=True)

    y = 490
    for line in cv["headline"]:
        _t(c, line, M, y, "SansXB", 30, TEXT_L)
        y -= 38
    y -= 14
    for i, line in enumerate(cv["headline_accent"]):
        _t(c, line, M, y, "SansXB", 30, ACCENT_L if i == len(cv["headline_accent"]) - 1 else TEXT_L)
        y -= 38
    draw_text(c, cv["sub"], M, 300, 400, size=10, leading=17, color=MUTED_L)
    _t(c, doc.data["name"], M, 190, "SansXB", 19, TEXT_L)
    _t(c, "Jonggeol Park", M, 172, "Sans", 8.5, MUTED_L)

    # Portrait from the site, cropped to fill a fixed box so it never letterboxes.
    photo = base.cached_image(doc.data["site"], doc.data["photo"], 600, doc.quality) if doc.data.get("photo") else None
    px, pw, ptop, ph = 500, RIGHT - 500, 505, 330
    if photo:
        draw_image_cover(c, photo, px, ptop - ph, pw, ph, radius=4)
    _rule(c, px, RIGHT, 160, RULE_L)
    _t(c, "SELECTED EXPERIENCE", px, 146, "SansB", 6.5, ACCENT_L)
    yy = 126
    for line in cv["experience"]:
        _t(c, line, px, yy, "Sans", 8.5, TEXT_L)
        yy -= 16
    _t(c, cv["tags"], px, yy - 6, "Sans", 7.2, MUTED_L)


def render_profile(doc, content):
    c, d, pf = doc.c, doc.data, content["profile"]
    _page(doc, "page-profile", pf["label"])

    _t(c, pf["headline"][0], M, 500, "SansXB", 21, TEXT)
    _t(c, pf["headline"][1], M, 473, "SansXB", 21, TEXT)
    _t(c, d["name"], M, 428, "SansXB", 18, TEXT)
    _t(c, "Jonggeol Park", M + pdfmetrics.stringWidth(d["name"], "SansXB", 18) + 14, 428, "Sans", 8.5, MUTED)

    # Left: experience from the site. Vertical flow follows the drawn text.
    _t(c, "EXPERIENCE", M, 376, "SansB", 6.5, ACCENT)
    yy = 346
    for exp in d.get("experience") or []:
        _t(c, exp["company"], M, yy, "SansXB", 14, TEXT)
        _t(c, exp["period"], M + 124, yy, "Sans", 7.5, MUTED)
        yy, _ = draw_text(c, exp.get("role") or "", M, yy - 23, 360, size=8.3, leading=12, font="SansB")
        body = " · ".join(exp.get("bullets") or [])
        yy, _ = draw_text(c, body, M, yy - 17, 360, size=8, leading=13.5, color=MUTED, max_lines=3)
        yy -= 48
        if yy < 120:
            break

    # Right: education + language, then recognition (most recent first).
    x = COL2
    _t(c, "EDUCATION / LANGUAGE", x, 376, "SansB", 6.5, ACCENT)
    ry = 350
    for edu in d.get("education") or []:
        line = " ".join(s for s in (edu.get("main"), edu.get("sub")) if s)
        _t(c, f"{line} / {edu.get('period', '')}".strip(" /"), x, ry, "Sans", 8.2, TEXT)
        ry -= 18
    for lang in d.get("language") or []:
        line = " ".join(s for s in (lang.get("main"), lang.get("sub")) if s)
        period = lang.get("period") or ""
        _t(c, f"{line} / {period}".strip(" /"), x, ry, "Sans", 8.2, TEXT)
        ry -= 18

    ry -= 28
    _t(c, "SELECTED RECOGNITION", x, ry, "SansB", 6.5, ACCENT)
    ry -= 24
    for aw in _awards_desc(d.get("awards") or []):
        year = _year(aw.get("period") or aw.get("main") or "")
        main = aw.get("main") or ""
        line = main if main.startswith(str(year)) else f"{year} {main}".strip()
        ry, _ = draw_text(c, line, x, ry, COL_W, size=8.2, leading=12, max_lines=1)
        ry -= 18
        if ry < 110:
            break

    # Compact contact line that follows the content instead of sitting at a
    # fixed height (no empty band); the full contact block with QR is on the EOD page.
    cy = max(90, min(yy + 20, ry) - 30)
    _rule(c, M, RIGHT, cy, RULE)
    xx = M
    for label, url in ((d.get("email"), f"mailto:{d.get('email')}"),
                       (d["site"].replace("https://", ""), d["site"]),
                       ("LinkedIn / Jonggeol Park", d.get("linkedin"))):
        if label:
            xx = _arrow_link(c, label, xx, cy - 20, url=url)


def _year(s):
    m = re.search(r"(20\d\d|19\d\d)", s or "")
    return int(m.group(1)) if m else 0


def _awards_desc(awards):
    return sorted(awards, key=lambda a: _year(a.get("period") or a.get("main") or ""), reverse=True)


def render_overview(doc, content, first_project_page, tail_page):
    c, ov = doc.c, content["overview"]
    _page(doc, "page-overview", ov["label"])

    _t(c, ov["headline"], M, 497, "SansXB", 22, TEXT)
    draw_text(c, ov["sub"], M, 470, 700, size=9, leading=14, color=MUTED)

    col_w, gap = 245, 20
    for i, (value, label) in enumerate(ov["stats"]):
        x = M + i * (col_w + gap)
        _rule(c, x, x + col_w, 440, ACCENT, 1.5)
        _t(c, value, x, 405, "SansXB", 28, TEXT)
        draw_text(c, label, x, 385, col_w, size=8.5, leading=13, color=MUTED)

    _t(c, ov["work_label"], M, 322, "SansB", 6.5, ACCENT)
    y = 300
    for g in ov["groups"]:
        if g.get("tail"):
            first, last = tail_page, tail_page + 2
        else:
            first = first_project_page + g["first_project"]
            last = first + g["count"] - 1
        _t(c, g["num"], M, y, "SansB", 8, ACCENT)
        _t(c, g["title"], M + 40, y, "SansB", 9, TEXT)
        _t(c, g["items"], 330, y, "Sans", 8.2, MUTED)
        _rt(c, f"{first:02d} - {last:02d}", RIGHT, y, "SansB", 7.5, TEXT)
        _rule(c, M, RIGHT, y - 14, RULE)
        _link_in(c, f"page-{first}", M, y - 12, RIGHT - M, 28)
        y -= 42

    foot = ov["footnote"].replace("{date}", f"{date.today():%Y.%m.%d}")
    draw_text(c, foot, M, 52, RIGHT - M, size=6.6, leading=10, color=MUTED, max_lines=2)


def render_project(doc, content, idx, total, pj):
    """One claim-headline project page. Left: media + stats + links. Right: sections."""
    c = doc.c
    site = _site_project(doc, pj["site_title"])
    _page(doc, f"page-{doc.page_no + 1}", pj["label"])

    _rt(c, f"{idx:02d} / {total:02d}", RIGHT, 508, "SansB", 8, ACCENT)
    _t(c, pj["headline"][0], M, 500, "SansXB", 21, TEXT)
    _t(c, pj["headline"][1], M, 473, "SansXB", 21, TEXT)
    _t(c, pj["name"], M, 440, "SansB", 10.5, ACCENT)
    _t(c, (site or {}).get("period") or "", COL2, 440, "Sans", 8.5, MUTED)

    # Left column media. Hero is always a 16:9 crop-to-fill box; the row below
    # is two cropped thumbnails when the site has them, otherwise topic chips.
    lx, lw = M, 350
    hero_top = 420
    # Media tiles under the hero, in priority order: curated stills committed
    # under data/astra_tiles, then the site's own extra images, then the
    # project's YouTube videos (for projects the site holds a single still of).
    # A tile entry is a filename, or {"file": ..., "focus": 0..1} to say which
    # band of a tall still to keep.
    tiles, focuses = [], []
    for entry in pj.get("tiles") or []:
        name = entry if isinstance(entry, str) else entry.get("file")
        path = cached_local_tile(name, 340, doc.quality)
        if path:
            tiles.append(path)
            focuses.append(None if isinstance(entry, str) else entry.get("focus"))
    if not tiles:
        tiles = [t for t in (_image(doc, site, i, 340) for i in (1, 2, 3)) if t]
        for vid in pj.get("videos") or []:
            if len(tiles) >= 3:
                break
            t = cached_youtube_thumb(vid, 340, doc.quality)
            if t:
                tiles.append(t)
        focuses = [None] * len(tiles)
    tiles, focuses = tiles[:3], focuses[:3]

    # Only genuinely tall stills switch the row to tall cells. Near-square site
    # photos (~0.75) must not, or they drag the hero into a squashed band.
    vertical = sum(1 for t in tiles if _aspect(t) < 0.7) >= 2
    # Vertical stills need tall cells, so the hero gives up height to them.
    # Otherwise the hero is a true 16:9 box, which a video still fills uncropped.
    hero_h, tile_h = (140, 120) if vertical else (197, 63)
    hero = _image(doc, site, 0, 700)
    if hero:
        # `hero_focus` says which band of the still to keep when the box is
        # shorter than the source — e.g. 1.0 to hold on to a caption at its foot.
        draw_image_cover(c, hero, lx, hero_top - hero_h, lw, hero_h, radius=3,
                         focus_y=pj.get("hero_focus", 0.35))
    row_top = hero_top - hero_h - 8
    if len(tiles) >= 2:
        n = len(tiles)
        tw = (lw - 8 * (n - 1)) / n
        if vertical:
            th = tile_h
        else:
            # Match the widest source so nothing is cropped off the sides — a
            # 2:1 frame in a 16:9 cell would lose the ends of its caption.
            th = min(tile_h, round(tw / max(_aspect(t) for t in tiles)))
        for i, t in enumerate(tiles):
            a = _aspect(t)
            # a tall still keeps its subject band (0.35); a portrait screenshot
            # keeps its picture, not its caption (0.18); landscape stays centred
            focus = focuses[i]
            if focus is None:
                focus = 0.35 if a < 0.8 else (0.18 if a < 1.0 else 0.5)
            draw_image_cover(c, t, lx + i * (tw + 8), row_top - th, tw, th, radius=3, focus_y=focus)
    elif pj.get("chips"):
        cw, ch = (lw - 16) / 3, 24
        for i, chip in enumerate(pj["chips"][:3]):
            x = lx + i * (cw + 8)
            c.setFillColor(CHIP)
            c.rect(x, row_top - ch, cw, ch, stroke=0, fill=1)
            _t(c, chip, x + 10, row_top - ch + 8, "Sans", 7.2, TEXT)

    # Stats
    stat_w = lw / 3
    for i, (value, label) in enumerate(pj["stats"][:3]):
        x = lx + i * stat_w
        size = 24 if pdfmetrics.stringWidth(value, "SansXB", 24) <= stat_w - 8 else 19
        _t(c, value, x, 112, "SansXB", size, TEXT)
        draw_text(c, label, x, 94, stat_w - 8, size=7.6, leading=11.5, color=MUTED, max_lines=2)

    # Links
    xx = lx
    for label, url in _link_urls(site, pj.get("links") or [])[:2]:
        xx = _arrow_link(c, label, xx, 62, url=url)

    # Footnote
    draw_text(c, pj.get("footnote") or "", M, 46, RIGHT - M, size=6.4, leading=9.5, color=MUTED, max_lines=2)

    # Right column sections, flowing from the top.
    y = 406
    for label, body in pj["sections"]:
        _t(c, label, COL2, y, "SansB", 7.2, ACCENT)
        y, _ = draw_text(c, body, COL2, y - 16, COL_W, size=8.7, leading=13.2, max_lines=4)
        y -= 26

    # Highlight block anchored near the bottom of the column.
    hy = min(150, y - 4)
    _rule(c, COL2, RIGHT, hy, ACCENT, 0.8)
    _t(c, pj["highlight"][0], COL2, hy - 22, "SansB", 9.5, TEXT)
    draw_text(c, pj["highlight"][1], COL2, hy - 38, COL_W, size=8.3, leading=11.5, color=MUTED, max_lines=2)
    role = (site or {}).get("role") or ""
    _t(c, "역할", COL2, 68, "SansB", 7.5, MUTED)
    _t(c, role, COL2 + 26, 68, "Sans", 7.5, MUTED)


def render_production(doc, content):
    c, pr = doc.c, content["production"]
    _page(doc, f"page-{doc.page_no + 1}", pr["label"])

    _t(c, pr["headline"], M, 500, "SansXB", 21, TEXT)
    draw_text(c, pr["sub"], M, 475, 700, size=9, leading=14, color=MUTED)

    card_w = COL_W
    img_h = round(card_w * 9 / 16)       # 209
    for i, card in enumerate(pr["cards"][:2]):
        x = M + i * (card_w + 18)
        site = _site_project(doc, card["site_title"])
        img = _image(doc, site, 0, 700)
        if img:
            draw_image_cover(c, img, x, 440 - img_h, card_w, img_h, radius=3)
        _t(c, card["name"], x, 205, "SansXB", 13, TEXT)
        _rt(c, card["period"], x + card_w, 205, "Sans", 8, MUTED)
        draw_text(c, card["desc"], x, 182, card_w, size=8, leading=13, max_lines=2)
        value, label = card["stat"]
        _t(c, value, x, 118, "SansXB", 24, ACCENT)
        vw = pdfmetrics.stringWidth(value, "SansXB", 24)
        draw_text(c, label, x + vw + 14, 126, card_w - vw - 14, size=8, leading=11.5, color=MUTED, max_lines=2)
        xx = x
        for lab, url in _link_urls(site, card.get("links") or [])[:2]:
            xx = _arrow_link(c, lab, xx, 70, url=url)

    draw_text(c, pr.get("footnote") or "", M, 48, RIGHT - M, size=6.4, leading=9.5, color=MUTED, max_lines=2)


def render_method(doc, content, first_project_page):
    c, me = doc.c, content["method"]
    _page(doc, f"page-{doc.page_no + 1}", me["label"], dark=True)

    _t(c, me["headline"][0], M, 498, "SansXB", 22, TEXT_L)
    _t(c, me["headline"][1], M, 470, "SansXB", 22, TEXT_L)

    col_w, gap = 232, 30
    for i, st in enumerate(me["steps"][:3]):
        x = M + i * (col_w + gap)
        _t(c, st["num"], x, 366, "SansXB", 34, ACCENT_L)
        _rule(c, x, x + col_w, 334, RULE_L)
        _t(c, st["title"], x, 311, "SansB", 12, TEXT_L)
        draw_text(c, st["body"], x, 284, col_w, size=8.7, leading=13.5, color=MUTED_L)
        _t(c, f"실제 적용  /  {st['case']}", x, 222, "SansB", 6.8, ACCENT_L)
        y, _ = draw_text(c, st["applied"], x, 204, col_w, size=8.2, leading=12.5, color=TEXT_L, max_lines=4)
        y -= 20
        for line in st["result"].split("\n"):
            _t(c, "→ " + line, x, y, "SansB", 8, ACCENT_L)
            y -= 12
        _arrow_link(c, "사례로 이동", x, y - 14, dest=f"page-{first_project_page + st['project']}",
                    color=TEXT_L)


def render_eod(doc, content):
    c, d, eo = doc.c, doc.data, content["eod"]
    _page(doc, f"page-{doc.page_no + 1}", "END OF DOCUMENT", dark=True)

    _t(c, eo["mark"], M, 430, "SansXB", 58, ACCENT_L)
    _t(c, eo["headline"][0], M, 370, "SansXB", 22, TEXT_L)
    _t(c, eo["headline"][1], M, 342, "SansXB", 22, TEXT_L)
    draw_text(c, eo["sub"], M, 300, 420, size=9.5, leading=15.5, color=MUTED_L)

    y = 200
    rows = (("EMAIL", d.get("email"), f"mailto:{d.get('email')}"),
            ("PORTFOLIO", d["site"].replace("https://", ""), d["site"]),
            ("LINKEDIN", (d.get("linkedin") or "").replace("https://", "").replace("www.", ""), d.get("linkedin")))
    for label, value, url in rows:
        if not value:
            continue
        _t(c, label, M, y, "SansB", 6.5, ACCENT_L)
        _t(c, value, M + 80, y, "Sans", 9, TEXT_L)
        _link_out(c, url, M + 80, y - 3, pdfmetrics.stringWidth(value, "Sans", 9), 14)
        y -= 26

    qx, qs = RIGHT - 96, 96
    _qr(c, d["site"], qx, 110, qs)
    draw_text(c, eo["site_note"], COL2, 160, qx - COL2 - 24, size=8, leading=12.5, color=MUTED_L)


# ── Document assembly ─────────────────────────────────────────────────

def build(doc, content):
    """Render the whole astra document. Returns (page_count, {project_index: page_no})."""
    n_proj = len(content["projects"])
    first_project_page = 4                       # cover, profile, overview, then projects
    tail_page = first_project_page + n_proj      # production page

    render_cover(doc, content)
    render_profile(doc, content)
    render_overview(doc, content, first_project_page, tail_page)
    started = {}
    for i, pj in enumerate(content["projects"], 1):
        started[i] = doc.page_no + 1
        render_project(doc, content, i, n_proj, pj)
    render_production(doc, content)
    render_method(doc, content, first_project_page)
    render_eod(doc, content)
    doc.c.save()
    return doc.page_no, started
