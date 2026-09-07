# -*- coding: utf-8 -*-
"""Build a general-purpose portfolio PDF from the live portfolio site.

The site (DB + admin edits) stays the source of truth; this script scrapes the public
page, downloads the images it needs, and lays everything out as a landscape A4 PDF that
mirrors the site's editorial look. Every link on the site becomes a clickable link in the
PDF, and the site URL (plus a QR code) is printed on the cover and closing pages.

Usage:
    python tools/build_general_portfolio_pdf.py                 # Korean, from jgpark.up.railway.app
    python tools/build_general_portfolio_pdf.py --lang en       # English page
    python tools/build_general_portfolio_pdf.py --url http://localhost:5050 --out /tmp/test.pdf

Fonts (Nanum Gothic / Nanum Myeongjo, OFL) and images are cached under pdf/ (git-ignored).
"""
import argparse
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph, Spacer, Table, TableStyle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(ROOT, 'pdf')
FONT_DIR = os.path.join(PDF_DIR, 'fonts')
CACHE_DIR = os.path.join(PDF_DIR, 'cache')
DEFAULT_SITE = 'https://jgpark.up.railway.app'
MAX_IMAGE_PX = 1400  # longest edge of embedded images; keeps the PDF a few MB
FONT_SOURCES = {
    'NanumGothic-Regular.ttf': 'nanumgothic/NanumGothic-Regular.ttf',
    'NanumGothic-Bold.ttf': 'nanumgothic/NanumGothic-Bold.ttf',
    'NanumGothic-ExtraBold.ttf': 'nanumgothic/NanumGothic-ExtraBold.ttf',
    'NanumMyeongjo-Regular.ttf': 'nanummyeongjo/NanumMyeongjo-Regular.ttf',
    'NanumMyeongjo-Bold.ttf': 'nanummyeongjo/NanumMyeongjo-Bold.ttf',
    'NanumMyeongjo-ExtraBold.ttf': 'nanummyeongjo/NanumMyeongjo-ExtraBold.ttf',
}
FONT_BASE_URL = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'

# ── Palette (mirrors static/css/main.css) ─────────────────────────────
BG = HexColor('#f6f1e9')
BG_ALT = HexColor('#efe7d9')
SURFACE = HexColor('#fdfaf5')
BORDER = HexColor('#e4dac9')
TEXT = HexColor('#2a2320')
TEXT_2 = HexColor('#5c5147')
MUTED = HexColor('#9c8f7e')
ACCENT = HexColor('#c25e3a')
ACCENT_LIGHT = HexColor('#f6e8df')
OLIVE = HexColor('#5c5f3f')
OLIVE_LIGHT = HexColor('#eef0e5')
OLIVE_BORDER = HexColor('#d5dabf')
OLIVE_TEXT = HexColor('#474a2e')
DARK = HexColor('#1a1814')

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 40
FOOTER_H = 26

LABELS = {
    'ko': {
        'portfolio': 'PORTFOLIO', 'profile': '프로필', 'about': '소개', 'experience': '경력 사항',
        'education': '학력', 'language': '어학', 'awards': '수상내역', 'skills': '핵심 역량',
        'tools': '스킬', 'projects': '주요 프로젝트', 'key_results': '핵심 성과',
        'details': '상세 설명', 'resources': '관련 자료', 'videos': '영상',
        'summary': '개요', 'role': '역할', 'site_note': '이 PDF는 포트폴리오 사이트의 내용을 기준으로 만들었습니다. 영상과 최신 내용은 사이트에서 바로 확인하실 수 있습니다.',
        'visit': '포트폴리오 사이트에서 더 보기', 'contact': '연락처', 'email': '이메일',
        'linkedin': 'LinkedIn', 'generated': '기준일', 'continued': '(계속)',
        'closing_title': '감사합니다.', 'closing_sub': '영상, 링크, 갤러리를 포함한 전체 포트폴리오는 아래 사이트에서 보실 수 있습니다.',
        'page': '',
    },
    'en': {
        'portfolio': 'PORTFOLIO', 'profile': 'Profile', 'about': 'About', 'experience': 'Work Experience',
        'education': 'Education', 'language': 'Language', 'awards': 'Awards', 'skills': 'Core Competencies',
        'tools': 'Skills', 'projects': 'Featured Projects', 'key_results': 'Key results',
        'details': 'Project details', 'resources': 'Resources', 'videos': 'Videos',
        'summary': 'Overview', 'role': 'Role', 'site_note': 'This PDF is generated from the portfolio website. Videos and the latest updates are available on the site.',
        'visit': 'See more on the portfolio site', 'contact': 'Contact', 'email': 'Email',
        'linkedin': 'LinkedIn', 'generated': 'As of', 'continued': '(cont.)',
        'closing_title': 'Thank you.', 'closing_sub': 'The full portfolio, including videos, links, and the gallery, is on the site below.',
        'page': '',
    },
}


# ── Fetching ──────────────────────────────────────────────────────────

def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'portfolio-pdf-builder/1.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    return data if binary else data.decode('utf-8', 'replace')


def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, path in FONT_SOURCES.items():
        target = os.path.join(FONT_DIR, name)
        if os.path.exists(target) and os.path.getsize(target) > 100_000:
            continue
        print(f'  downloading font {name}')
        with open(target, 'wb') as fh:
            fh.write(fetch(FONT_BASE_URL + path, binary=True))
    pdfmetrics.registerFont(TTFont('Sans', os.path.join(FONT_DIR, 'NanumGothic-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('SansB', os.path.join(FONT_DIR, 'NanumGothic-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('SansXB', os.path.join(FONT_DIR, 'NanumGothic-ExtraBold.ttf')))
    pdfmetrics.registerFont(TTFont('Serif', os.path.join(FONT_DIR, 'NanumMyeongjo-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('SerifB', os.path.join(FONT_DIR, 'NanumMyeongjo-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('SerifXB', os.path.join(FONT_DIR, 'NanumMyeongjo-ExtraBold.ttf')))
    pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansB', italic='Sans', boldItalic='SansB')
    pdfmetrics.registerFontFamily('Serif', normal='Serif', bold='SerifB', italic='Serif', boldItalic='SerifB')


def cached_image(site, filename):
    """Download an uploaded image once; return a local path or None."""
    if not filename:
        return None
    os.makedirs(CACHE_DIR, exist_ok=True)
    target = os.path.join(CACHE_DIR, os.path.basename(filename))
    target = os.path.splitext(target)[0] + '.jpg'   # always stored as a downscaled JPEG
    if not os.path.exists(target) or os.path.getsize(target) < 1000:
        try:
            data = fetch(f'{site}/static/uploads/{filename}', binary=True)
        except Exception as exc:
            print(f'  image skipped {filename}: {exc}')
            return None
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im = im.convert('RGB')
            im.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
            im.save(target, 'JPEG', quality=82, optimize=True)
        except Exception as exc:
            print(f'  image skipped {filename}: {exc}')
            return None
    try:
        ImageReader(target).getSize()
    except Exception:
        return None
    return target


# ── Scraping the public page ─────────────────────────────────────────

def _text(fragment):
    fragment = re.sub(r'<br\s*/?>', '\n', fragment)
    fragment = re.sub(r'<[^>]+>', '', fragment)
    return html.unescape(fragment).strip()


def _attr(tag_html, name):
    m = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', tag_html)
    return html.unescape(m.group(1)) if m else ''


def _section(page, start_pattern, end_pattern):
    m = re.search(start_pattern, page)
    if not m:
        return ''
    rest = page[m.end():]
    e = re.search(end_pattern, rest)
    return rest[:e.start()] if e else rest


def _list_items(block):
    items = []
    for li in re.findall(r'<li class="about-list-item">(.*?)</li>', block, re.S):
        items.append({
            'period': _text(_section(li, r'class="ali-period">', r'</span>')),
            'main': _text(_section(li, r'class="ali-main">', r'</span>')),
            'sub': re.sub(r'^[·\s]+', '', _text(_section(li, r'class="ali-sub">', r'</span>'))),
        })
    return items


def scrape(site, lang):
    return parse(fetch(site + ('/en' if lang == 'en' else '/')), site, lang)


def parse(page, site, lang):
    """Turn the public page's HTML into the data the layout needs."""
    data = {'site': site, 'lang': lang}

    hero = _section(page, r'<section[^>]*class="hero', r'</section>')
    data['name'] = _text(_section(hero, r'class="hn-name">', r'</span>')) or 'Portfolio'
    data['role'] = _text(_section(hero, r'class="hero-role">', r'</span>'))
    data['tagline'] = _text(_section(hero, r'<p class="hero-sub">', r'</p>'))
    photo = re.search(r'class="hero-photo-frame">\s*<img src="[^"]*/uploads/([^"]+)"', hero)
    data['photo'] = photo.group(1) if photo else ''

    about = _section(page, r'id="about"', r'<section')
    data['about'] = [_text(p) for p in re.findall(r'<p>(.*?)</p>', _section(about, r'class="about-intro', r'</div>'), re.S)]
    blocks = re.split(r'<h4 class="about-block-title"[^>]*>', about)
    data['education'], data['language'], data['awards'] = [], [], []
    for b in blocks[1:]:
        title = _text(b.split('</h4>', 1)[0])
        body = b.split('</h4>', 1)[1] if '</h4>' in b else ''
        items = _list_items(body)
        if title in ('학력', 'Education'):
            data['education'] = items
        elif title in ('어학', 'Language'):
            data['language'] = items
        elif title in ('수상내역', 'Awards'):
            data['awards'] = items
    skills_block = _section(about, r'<ul class="skill-list">', r'</ul>')
    data['skills'] = [_text(s) for s in re.findall(r'class="skill-tag">(.*?)</span>', skills_block)]
    tools_block = _section(about, r'<ul class="skill-level-list">', r'</ul>')
    data['tools'] = [(_text(n), _text(l)) for n, l in re.findall(
        r'class="skill-tag">(.*?)</span>\s*<span class="level-badge[^"]*">(.*?)</span>', tools_block)]

    exp_block = _section(page, r'id="experience"', r'</section>')
    data['experience'] = []
    for chunk in re.split(r'<div class="timeline-item[^"]*">', exp_block)[1:]:
        data['experience'].append({
            'company': _text(_section(chunk, r'class="tl-company">', r'</span>')),
            'period': _text(_section(chunk, r'class="tl-period">', r'</span>')),
            'role': _text(_section(chunk, r'class="tl-role">', r'</div>')),
            'bullets': [_text(b) for b in re.findall(r'<li>(.*?)</li>', _section(chunk, r'<ul class="tl-desc">', r'</ul>'), re.S)],
        })

    data['projects'] = []
    for card in re.findall(r'<article class="project-card[^>]*>', page, re.S):
        try:
            links = json.loads(_attr(card, 'data-links') or '[]')
        except ValueError:
            links = []
        try:
            images = json.loads(_attr(card, 'data-images') or '[]')
        except ValueError:
            images = []
        data['projects'].append({
            'title': _attr(card, 'data-title'), 'period': _attr(card, 'data-period'),
            'desc': _attr(card, 'data-desc'), 'detail': _attr(card, 'data-detail'),
            'kpi': _attr(card, 'data-kpi'), 'role': _attr(card, 'data-myrole'),
            'category': _attr(card, 'data-category'), 'links': links, 'images': images,
            'tags': _attr(card, 'data-tags'),
        })

    contact = _section(page, r'id="contact"', r'</section>')
    m = re.search(r'href="mailto:([^"]+)"', contact)
    data['email'] = html.unescape(m.group(1)) if m else ''
    m = re.search(r'href="(https?://[^"]*linkedin[^"]*)"', contact)
    data['linkedin'] = html.unescape(m.group(1)) if m else ''
    return data


# ── Text helpers ─────────────────────────────────────────────────────

def esc(s):
    return html.escape(s or '', quote=False)


def split_kpi(raw):
    tiles, bullets = [], []
    for line in (raw or '').replace('\r', '').split('\n'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^(.+?)\s*[|｜]\s*(.+)$', line)
        if m:
            tiles.append((m.group(1).strip(), m.group(2).strip()))
        else:
            bullets.append(re.sub(r'^[-•·]\s*', '', line))
    return tiles, bullets


def youtube_id(url):
    m = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def is_playlist(url):
    return bool(re.search(r'[?&]list=', url or ''))


# ── Styles ────────────────────────────────────────────────────────────

def styles():
    S = {}
    S['body'] = ParagraphStyle('body', fontName='Sans', fontSize=9, leading=14.2, textColor=TEXT_2, alignment=TA_LEFT)
    S['body_small'] = ParagraphStyle('body_small', parent=S['body'], fontSize=8.4, leading=13.5)
    S['bullet'] = ParagraphStyle('bullet', parent=S['body'], leftIndent=10, bulletIndent=0, bulletFontName='Sans')
    S['h'] = ParagraphStyle('h', fontName='SansB', fontSize=8.2, leading=11, textColor=TEXT, spaceBefore=4, spaceAfter=6)
    S['sub'] = ParagraphStyle('sub', fontName='SansB', fontSize=9.4, leading=14, textColor=TEXT, spaceBefore=7, spaceAfter=2)
    S['desc'] = ParagraphStyle('desc', fontName='Sans', fontSize=10, leading=16.5, textColor=TEXT_2)
    S['desc_li'] = ParagraphStyle('desc_li', parent=S['desc'], leftIndent=10, bulletIndent=0)
    S['kpi_bullet'] = ParagraphStyle('kpi_bullet', fontName='SansB', fontSize=8.8, leading=13.5, textColor=OLIVE_TEXT, leftIndent=9, bulletIndent=0)
    S['kpi_value'] = ParagraphStyle('kpi_value', fontName='SerifXB', fontSize=14, leading=16, textColor=OLIVE_TEXT)
    S['kpi_label'] = ParagraphStyle('kpi_label', fontName='Sans', fontSize=7.4, leading=10, textColor=TEXT_2)
    S['link'] = ParagraphStyle('link', fontName='Sans', fontSize=8.4, leading=13, textColor=OLIVE)
    S['tl_company'] = ParagraphStyle('tl_company', fontName='SansB', fontSize=10, leading=14, textColor=TEXT)
    S['tl_period'] = ParagraphStyle('tl_period', fontName='Sans', fontSize=8, leading=11, textColor=MUTED)
    S['tl_role'] = ParagraphStyle('tl_role', fontName='SansB', fontSize=8.6, leading=12.5, textColor=ACCENT, spaceAfter=2)
    S['tl_bullet'] = ParagraphStyle('tl_bullet', parent=S['body_small'], leftIndent=9, bulletIndent=0)
    S['item_main'] = ParagraphStyle('item_main', fontName='SansB', fontSize=9, leading=13, textColor=TEXT)
    S['item_sub'] = ParagraphStyle('item_sub', fontName='Sans', fontSize=8, leading=11.5, textColor=TEXT_2)
    S['item_period'] = ParagraphStyle('item_period', fontName='Sans', fontSize=7.6, leading=11, textColor=MUTED)
    S['tag'] = ParagraphStyle('tag', fontName='SansB', fontSize=8, leading=11, textColor=ACCENT)
    return S


# ── Drawing primitives ───────────────────────────────────────────────

class Doc:
    def __init__(self, path, data, labels, total_pages=None):
        self.c = canvas.Canvas(path, pagesize=landscape(A4))
        self.data = data
        self.L = labels
        self.S = styles()
        self.total = total_pages
        self.page_no = 0
        self.c.setTitle(f"{data['name']} — Portfolio")
        self.c.setAuthor(data['name'])
        self.c.setSubject(f"Portfolio · {data['site']}")
        self.c.setCreator('portfolio site → PDF builder')

    # page chrome
    def begin_page(self, bg=BG):
        if self.page_no:
            self.c.showPage()
        self.page_no += 1
        self.c.setFillColor(bg)
        self.c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    def footer(self, label=''):
        c = self.c
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.6)
        c.line(MARGIN, FOOTER_H + 6, PAGE_W - MARGIN, FOOTER_H + 6)
        c.setFont('Sans', 7.2)
        c.setFillColor(MUTED)
        left = f"{self.data['name']} — Portfolio"
        if label:
            left += f'  ·  {label}'
        c.drawString(MARGIN, FOOTER_H - 6, left)
        site = self.data['site'].replace('https://', '').replace('http://', '')
        c.drawCentredString(PAGE_W / 2, FOOTER_H - 6, site)
        c.linkURL(self.data['site'], (PAGE_W / 2 - 80, FOOTER_H - 10, PAGE_W / 2 + 80, FOOTER_H + 2))
        right = f'{self.page_no}' + (f' / {self.total}' if self.total else '')
        c.drawRightString(PAGE_W - MARGIN, FOOTER_H - 6, right)

    def section_label(self, x, y, text):
        """Small accent dash + label, like .modal-h on the site."""
        c = self.c
        c.setFillColor(ACCENT)
        c.rect(x, y + 2.6, 9, 1.8, stroke=0, fill=1)
        c.setFont('SansB', 8.2)
        c.setFillColor(TEXT)
        c.drawString(x + 14, y, text)

    def image_box(self, path, x, y, w, h, bg=DARK, radius=6):
        """Draw an image with object-fit: contain inside a 16:9 box."""
        c = self.c
        c.setFillColor(bg)
        c.roundRect(x, y, w, h, radius, stroke=0, fill=1)
        if not path:
            return
        img = ImageReader(path)
        iw, ih = img.getSize()
        scale = min(w / iw, h / ih)
        dw, dh = iw * scale, ih * scale
        c.saveState()
        p = c.beginPath()
        p.roundRect(x, y, w, h, radius)
        c.clipPath(p, stroke=0)
        c.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask='auto')
        c.restoreState()

    def qr(self, url, x, y, size):
        import qrcode
        q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
        q.add_data(url)
        q.make(fit=True)
        matrix = q.get_matrix()
        n = len(matrix)
        cell = size / n
        c = self.c
        c.setFillColor(SURFACE)
        c.rect(x - 6, y - 6, size + 12, size + 12, stroke=0, fill=1)
        c.setFillColor(TEXT)
        for r, row in enumerate(matrix):
            for col, on in enumerate(row):
                if on:
                    c.rect(x + col * cell, y + size - (r + 1) * cell, cell, cell, stroke=0, fill=1)
        c.linkURL(url, (x - 6, y - 6, x + size + 6, y + size + 6))

    def flow(self, story, frame_factory, header_factory=None):
        """Lay out flowables into frames, adding continuation pages as needed."""
        story = list(story)
        first = True
        while story:
            if not first:
                self.begin_page()
                if header_factory:
                    header_factory(continued=True)
            frame = frame_factory()
            frame.addFromList(story, self.c)
            if story and not first and frame._atTop:  # nothing fit at all: avoid an infinite loop
                story.pop(0)
            first = False

    # ── pages ────────────────────────────────────────────────────────
    def cover(self):
        d, L, c = self.data, self.L, self.c
        self.begin_page()
        # hairline + eyebrow
        c.setStrokeColor(TEXT)
        c.setLineWidth(1)
        c.line(MARGIN, PAGE_H - 70, PAGE_W - MARGIN, PAGE_H - 70)
        c.setFont('Sans', 7.6)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, PAGE_H - 88, d['role'].upper() if d['lang'] == 'en' else d['role'])
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 88, f"{L['portfolio']} — {date.today().year}")

        photo = cached_image(d['site'], d['photo'])
        text_w = PAGE_W - 2 * MARGIN - (220 if photo else 0)
        y = PAGE_H - 175
        c.setFont('Serif', 20)
        c.setFillColor(TEXT_2)
        hello = 'Hello, I am' if d['lang'] == 'en' else '안녕하세요,'
        c.drawString(MARGIN, y + 46, hello)
        c.setFont('SerifXB', 46)
        c.setFillColor(TEXT)
        c.drawString(MARGIN, y, d['name'])
        name_w = pdfmetrics.stringWidth(d['name'], 'SerifXB', 46)
        c.setFont('Serif', 24)
        c.drawString(MARGIN + name_w + 8, y, '' if d['lang'] == 'en' else '입니다')
        c.setFillColor(ACCENT)
        suffix_w = 0 if d['lang'] == 'en' else pdfmetrics.stringWidth('입니다', 'Serif', 24)
        c.drawString(MARGIN + name_w + 8 + suffix_w, y, '.')

        # tagline with accent bar
        c.setFillColor(ACCENT)
        c.rect(MARGIN, y - 78, 2, 44, stroke=0, fill=1)
        para = Paragraph(esc(d['tagline']).replace('\n', '<br/>'),
                         ParagraphStyle('tag', fontName='Sans', fontSize=12, leading=19, textColor=TEXT_2))
        w, h = para.wrap(text_w - 18, 120)
        para.drawOn(c, MARGIN + 14, y - 34 - h + 8)

        if photo:
            fw, fh = 175, 225
            fx, fy = PAGE_W - MARGIN - fw, PAGE_H - 110 - fh
            c.setFillColor(SURFACE)
            c.setStrokeColor(BORDER)
            c.roundRect(fx - 4, fy - 4, fw + 8, fh + 8, 5, stroke=1, fill=1)
            img = ImageReader(photo)
            iw, ih = img.getSize()
            scale = max(fw / iw, fh / ih)
            dw, dh = iw * scale, ih * scale
            c.saveState()
            p = c.beginPath()
            p.roundRect(fx, fy, fw, fh, 4)
            c.clipPath(p, stroke=0)
            c.drawImage(img, fx + (fw - dw) / 2, fy + (fh - dh) / 2, dw, dh)
            c.restoreState()
            c.setFont('Sans', 7)
            c.setFillColor(MUTED)
            c.drawRightString(fx + fw, fy - 14, f"{d['name']} — Portfolio")

        # bottom band: site + contact + QR
        band_y = 70
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.6)
        c.line(MARGIN, band_y + 96, PAGE_W - MARGIN, band_y + 96)
        self.section_label(MARGIN, band_y + 72, L['visit'])
        c.setFont('SansB', 13)
        c.setFillColor(ACCENT)
        site_text = d['site'].replace('https://', '')
        c.drawString(MARGIN, band_y + 48, site_text)
        c.linkURL(d['site'], (MARGIN, band_y + 44, MARGIN + pdfmetrics.stringWidth(site_text, 'SansB', 13), band_y + 62))
        c.setFont('Sans', 8)
        c.setFillColor(TEXT_2)
        note = Paragraph(esc(L['site_note']), ParagraphStyle('n', fontName='Sans', fontSize=7.8, leading=11.5, textColor=MUTED))
        w, h = note.wrap(300, 60)
        note.drawOn(c, MARGIN, band_y + 44 - h - 2)

        cx = MARGIN + 340
        self.section_label(cx, band_y + 72, L['contact'])
        c.setFont('Sans', 9)
        c.setFillColor(TEXT_2)
        yy = band_y + 50
        if d['email']:
            c.drawString(cx, yy, f"{L['email']}   {d['email']}")
            c.linkURL('mailto:' + d['email'], (cx, yy - 3, cx + 260, yy + 10))
            yy -= 16
        if d['linkedin']:
            ln = d['linkedin'].replace('https://', '')
            c.drawString(cx, yy, f"{L['linkedin']}   {ln}")
            c.linkURL(d['linkedin'], (cx, yy - 3, cx + 260, yy + 10))
        self.qr(d['site'], PAGE_W - MARGIN - 78, band_y + 14, 78)
        self.footer()

    def profile(self):
        d, L, S, c = self.data, self.L, self.S, self.c
        self.begin_page()
        self.page_header(L['profile'])
        col_gap = 28
        col_w = (PAGE_W - 2 * MARGIN - col_gap) / 2
        top = PAGE_H - 110
        bottom = FOOTER_H + 16

        left = []
        left.append(Paragraph(esc(L['about']), S['h']))
        for p in d['about']:
            left.append(Paragraph(esc(p), S['desc']))
            left.append(Spacer(1, 6))
        left.append(Spacer(1, 8))
        left.append(Paragraph(esc(L['experience']), S['h']))
        for exp in d['experience']:
            block = [
                Table([[Paragraph(esc(exp['company']), S['tl_company']), Paragraph(esc(exp['period']), S['tl_period'])]],
                      colWidths=[col_w * 0.62, col_w * 0.38],
                      style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)])),
                Paragraph(esc(exp['role']), S['tl_role']),
            ]
            for b in exp['bullets']:
                block.append(Paragraph(esc(b), S['tl_bullet'], bulletText='·'))
            block.append(Spacer(1, 9))
            left.extend(block)

        right = []

        def item_list(title, items, with_period=True):
            if not items:
                return
            right.append(Paragraph(esc(title), S['h']))
            for it in items:
                rows = []
                if with_period and it.get('period'):
                    rows.append(Paragraph(esc(it['period']), S['item_period']))
                rows.append(Paragraph(esc(it['main']), S['item_main']))
                if it.get('sub'):
                    rows.append(Paragraph(esc(it['sub']), S['item_sub']))
                rows.append(Spacer(1, 5))
                right.extend(rows)
            right.append(Spacer(1, 6))

        item_list(L['education'], d['education'])
        item_list(L['language'], d['language'], with_period=False)
        item_list(L['awards'], d['awards'])
        if d['skills']:
            left.append(Spacer(1, 4))
            left.append(Paragraph(esc(L['skills']), S['h']))
            left.append(Paragraph('  ·  '.join(esc(x) for x in d['skills']), S['tag']))
            left.append(Spacer(1, 10))
        if d['tools']:
            left.append(Paragraph(esc(L['tools']), S['h']))
            left.append(Paragraph('  ·  '.join(f"{esc(n)} <font color='#9c8f7e'>{esc(l)}</font>" for n, l in d['tools']), S['tag']))

        # left column flows onto continuation pages if needed; right column is drawn on the first page only
        Frame(MARGIN + col_w + col_gap, bottom, col_w, top - bottom, leftPadding=0, rightPadding=0,
              topPadding=0, bottomPadding=0).addFromList(right, c)
        self.footer(L['profile'])
        self.flow(left,
                  lambda: Frame(MARGIN, bottom, col_w, top - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
                  header_factory=lambda continued: (self.page_header(L['profile'], continued), self.footer(L['profile'])))

    def page_header(self, label, continued=False):
        c, L = self.c, self.L
        c.setStrokeColor(TEXT)
        c.setLineWidth(1)
        c.line(MARGIN, PAGE_H - 44, PAGE_W - MARGIN, PAGE_H - 44)
        c.setFont('Sans', 7.6)
        c.setFillColor(MUTED)
        text = label + (f"  {L['continued']}" if continued else '')
        c.drawString(MARGIN, PAGE_H - 60, text)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 60, f"{self.data['name']} — {L['portfolio']}")

    def project(self, idx, p):
        d, L, S, c = self.data, self.L, self.S, self.c
        self.begin_page()
        total = len(d['projects'])
        label = f"{L['projects']}  {idx:02d} / {total:02d}"

        def header(continued=False):
            self.page_header(label, continued)
            if continued:
                c.setFont('SerifB', 13)
                c.setFillColor(TEXT)
                c.drawString(MARGIN, PAGE_H - 84, p['title'])
            self.footer(label)

        header()
        # title block
        eyebrow = '  ·  '.join(x for x in (p['category'], p['period']) if x)
        c.setFont('Sans', 7.8)
        c.setFillColor(MUTED)
        c.drawString(MARGIN, PAGE_H - 78, eyebrow)
        title = Paragraph(esc(p['title']), ParagraphStyle('t', fontName='SerifXB', fontSize=19, leading=24, textColor=TEXT))
        tw, th = title.wrap(PAGE_W - 2 * MARGIN - 200, 60)
        title.drawOn(c, MARGIN, PAGE_H - 84 - th)
        y = PAGE_H - 84 - th - 8
        if p['role']:
            c.setFont('SansB', 7.6)
            rw = pdfmetrics.stringWidth(p['role'], 'SansB', 7.6) + 14
            c.setFillColor(ACCENT_LIGHT)
            c.setStrokeColor(HexColor('#eccdbd'))
            c.roundRect(MARGIN, y - 12, rw, 15, 3, stroke=1, fill=1)
            c.setFillColor(ACCENT)
            c.drawString(MARGIN + 7, y - 8, p['role'])
            y -= 20

        # left column: image + summary + resources
        left_w = 292
        gap = 26
        right_x = MARGIN + left_w + gap
        right_w = PAGE_W - MARGIN - right_x
        top = y - 8
        bottom = FOOTER_H + 16

        img_h = left_w * 9 / 16
        main_img = cached_image(d['site'], p['images'][0] if p['images'] else '')
        self.image_box(main_img, MARGIN, top - img_h, left_w, img_h)
        ly = top - img_h - 10
        thumbs = [cached_image(d['site'], f) for f in p['images'][1:4]]
        thumbs = [t for t in thumbs if t]
        if thumbs:
            tw_ = (left_w - 6 * (len(thumbs) - 1)) / len(thumbs)
            th_ = tw_ * 9 / 16
            for i, t in enumerate(thumbs):
                self.image_box(t, MARGIN + i * (tw_ + 6), ly - th_, tw_, th_, radius=3)
            ly -= th_ + 10

        left = []
        left.append(Paragraph(esc(L['summary']), S['h']))
        desc_lines = [l.strip() for l in (p['desc'] or '').replace('\r', '').split('\n') if l.strip()]
        if len(desc_lines) > 1:
            for l in desc_lines:
                left.append(Paragraph(esc(re.sub(r'^[-•·]\s*', '', l)), S['desc_li'], bulletText='·'))
        elif desc_lines:
            left.append(Paragraph(esc(desc_lines[0]), S['desc']))
        links = [lk for lk in p['links'] if lk.get('url')]
        videos = [lk for lk in links if youtube_id(lk['url']) or is_playlist(lk['url'])]
        others = [lk for lk in links if lk not in videos]
        if videos:
            left.append(Spacer(1, 8))
            left.append(Paragraph(esc(L['videos']), S['h']))
            for lk in videos:
                left.append(Paragraph(f"▶ <a href=\"{esc(lk['url'])}\"><u>{esc(lk.get('label') or lk['url'])}</u></a>", S['link']))
        if others:
            left.append(Spacer(1, 8))
            left.append(Paragraph(esc(L['resources']), S['h']))
            for lk in others:
                left.append(Paragraph(f"→ <a href=\"{esc(lk['url'])}\"><u>{esc(lk.get('label') or lk['url'])}</u></a>", S['link']))
        Frame(MARGIN, bottom, left_w, ly - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0).addFromList(left, c)

        # right column: key results + details (flows to continuation pages)
        right = []
        tiles, bullets = split_kpi(p['kpi'])
        if tiles or bullets:
            right.append(Paragraph(esc(L['key_results']), S['h']))
            if tiles:
                cols = 3
                cell_w = (right_w - 6 * (cols - 1)) / cols
                rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
                for row in rows:
                    cells = []
                    for v, l in row:
                        cells.append([Paragraph(esc(v), S['kpi_value']), Paragraph(esc(l), S['kpi_label'])])
                    while len(cells) < cols:
                        cells.append('')
                    t = Table([cells], colWidths=[cell_w] * cols, hAlign='LEFT',
                              style=TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                                                ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                                                ('VALIGN', (0, 0), (-1, -1), 'TOP')]
                                               + [('BACKGROUND', (i, 0), (i, 0), OLIVE_LIGHT) for i, cell in enumerate(cells) if cell]
                                               + [('BOX', (i, 0), (i, 0), 0.6, OLIVE_BORDER) for i, cell in enumerate(cells) if cell]))
                    right.append(t)
                    right.append(Spacer(1, 6))
            for b in bullets:
                right.append(Paragraph(esc(b), S['kpi_bullet'], bulletText='•'))
            right.append(Spacer(1, 10))
        detail = (p['detail'] or '').replace('\r', '')
        if detail.strip():
            right.append(Paragraph(esc(L['details']), S['h']))
            pending = []

            def flush():
                nonlocal pending
                for item in pending:
                    right.append(Paragraph(esc(item), S['bullet'], bulletText='·'))
                pending = []

            for line in detail.split('\n'):
                s = line.strip()
                if not s:
                    flush()
                    continue
                if re.match(r'^#{1,3}\s*', s):
                    flush()
                    right.append(Paragraph(esc(re.sub(r'^#{1,3}\s*', '', s)), S['sub']))
                elif re.match(r'^[-•·]\s+', s):
                    pending.append(re.sub(r'^[-•·]\s+', '', s))
                else:
                    flush()
                    right.append(Paragraph(esc(s), S['body']))
                    right.append(Spacer(1, 4))
            flush()
        avail = top - bottom
        need = sum(f.wrap(right_w, 10000)[1] + f.getSpaceBefore() + f.getSpaceAfter() for f in right)
        if avail < need <= avail * 1.22:
            for f in right:
                if isinstance(f, Paragraph):
                    st = ParagraphStyle('s', parent=f.style, fontSize=f.style.fontSize * 0.9, leading=f.style.leading * 0.88)
                    f.style = st
                    f.__init__(f.text, st, bulletText=getattr(f, 'bulletText', None))
        self.flow(right,
                  lambda: Frame(right_x if self.page_no == first_page else MARGIN, bottom,
                                right_w if self.page_no == first_page else PAGE_W - 2 * MARGIN,
                                (top if self.page_no == first_page else PAGE_H - 100) - bottom,
                                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
                  header_factory=header)
        return

    def closing(self):
        d, L, c = self.data, self.L, self.c
        self.begin_page(bg=BG_ALT)
        c.setFont('SerifXB', 30)
        c.setFillColor(TEXT)
        c.drawString(MARGIN, PAGE_H - 150, L['closing_title'])
        sub = Paragraph(esc(L['closing_sub']), ParagraphStyle('s', fontName='Sans', fontSize=11, leading=18, textColor=TEXT_2))
        w, h = sub.wrap(420, 100)
        sub.drawOn(c, MARGIN, PAGE_H - 165 - h)
        c.setFont('SansB', 16)
        c.setFillColor(ACCENT)
        site_text = d['site'].replace('https://', '')
        c.drawString(MARGIN, PAGE_H - 225 - h, site_text)
        c.linkURL(d['site'], (MARGIN, PAGE_H - 230 - h, MARGIN + pdfmetrics.stringWidth(site_text, 'SansB', 16), PAGE_H - 208 - h))
        c.setFont('Sans', 9.5)
        c.setFillColor(TEXT_2)
        yy = PAGE_H - 260 - h
        if d['email']:
            c.drawString(MARGIN, yy, f"{L['email']}   {d['email']}")
            c.linkURL('mailto:' + d['email'], (MARGIN, yy - 3, MARGIN + 300, yy + 11))
            yy -= 17
        if d['linkedin']:
            ln = d['linkedin'].replace('https://', '')
            c.drawString(MARGIN, yy, f"{L['linkedin']}   {ln}")
            c.linkURL(d['linkedin'], (MARGIN, yy - 3, MARGIN + 300, yy + 11))
        self.qr(d['site'], PAGE_W - MARGIN - 150, PAGE_H - 300, 150)
        c.setFont('Sans', 7.6)
        c.setFillColor(MUTED)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 318, f"{L['generated']} {date.today().isoformat()}")
        self.footer()

    def build(self):
        global first_page
        self.cover()
        self.profile()
        for i, p in enumerate(self.data['projects'], 1):
            first_page = self.page_no + 1
            self.project(i, p)
        self.closing()
        self.c.save()
        return self.page_no


first_page = 0


def build(site, lang, out):
    ensure_fonts()
    print('scraping', site, lang)
    data = scrape(site, lang)
    print(f"  {data['name']} · {len(data['projects'])} projects · {len(data['experience'])} jobs")
    labels = LABELS[lang]
    # two passes so the footer can show "page / total"
    tmp = out + '.tmp'
    total = Doc(tmp, data, labels).build()
    Doc(out, data, labels, total_pages=total).build()
    os.remove(tmp)
    print('wrote', out, f'({total} pages, {os.path.getsize(out) // 1024} KB)')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default=DEFAULT_SITE, help='portfolio site origin')
    ap.add_argument('--lang', choices=['ko', 'en'], default='ko')
    ap.add_argument('--out', default=None, help='output PDF path')
    args = ap.parse_args()
    out = args.out or os.path.join(PDF_DIR, f"portfolio_{args.lang}.pdf")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    try:
        build(args.url.rstrip('/'), args.lang, out)
    except urllib.error.URLError as exc:
        sys.exit(f'network error: {exc}')
