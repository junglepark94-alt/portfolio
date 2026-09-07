import io
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).parents[1]
DATA_PATH = ROOT / "data" / "hyundai_application_2026.json"
SOURCE_PDF = Path("D:/박종걸/박종걸_포트폴리오_2026.pdf")
ASSET_DIR = ROOT / "pdf" / "assets"
OUTPUT_PDF = Path(
    "C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/"
    "박종걸_현대자동차_포트폴리오_2026.pdf"
)

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 44
BG = HexColor("#F7F3EA")
SURFACE = HexColor("#EEE7DA")
TEXT = HexColor("#29221F")
MUTED = HexColor("#756B64")
ACCENT = HexColor("#C45E3A")
ACCENT_DARK = HexColor("#8C3F27")
WHITE = HexColor("#FFFFFF")
LINE = HexColor("#D8CCBB")


def register_fonts():
    pdfmetrics.registerFont(TTFont("Noto", "C:/Windows/Fonts/NotoSansKR-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("NotoM", "C:/Windows/Fonts/NotoSansKR-Medium.ttf"))


def extract_source_assets():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(SOURCE_PDF)
    page_map = {
        "portrait": 0,
        "banana_salon": 3,
        "binggraeus_youtube": 4,
        "binggraeus_instagram": 5,
        "wish_kingdom_popup": 6,
        "secret_semester": 7,
        "k_spiciest_cup": 8,
        "hells_gimbap": 9,
        "world_war_chef": 10,
        "mountain_city_women": 11,
        "shinee": 12,
    }
    for key, page_index in page_map.items():
        images = reader.pages[page_index].images
        if not images:
            continue
        image = images[0]
        extension = Path(image.name).suffix or ".jpg"
        (ASSET_DIR / f"{key}{extension}").write_bytes(image.data)

    gallery_dir = ASSET_DIR / "gallery"
    gallery_dir.mkdir(exist_ok=True)
    for index, image in enumerate(reader.pages[13].images[:9], start=1):
        extension = Path(image.name).suffix or ".jpg"
        (gallery_dir / f"gallery_{index:02d}{extension}").write_bytes(image.data)


def asset(key):
    matches = list(ASSET_DIR.glob(f"{key}.*"))
    return matches[0] if matches else None


def wrap_text(text, font, size, width):
    lines = []
    for paragraph in str(text).split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        if current:
            lines.append(current.rstrip())
    return lines


def draw_text(c, text, x, y, width, size=10, leading=16, font="Noto", color=TEXT, max_lines=None):
    text = str(text).replace("–", "-").replace("—", "-")
    c.setFont(font, size)
    c.setFillColor(color)
    lines = wrap_text(text, font, size, width)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_image_cover(c, image_path, x, y, width, height, radius=8):
    if not image_path or not Path(image_path).exists():
        c.setFillColor(SURFACE)
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


def page_frame(c, number, section="BRAND MARKETING PORTFOLIO"):
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, 27, PAGE_W - MARGIN, 27)
    c.setFont("Noto", 7.5)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 14, f"박종걸 · {section}")
    c.drawRightString(PAGE_W - MARGIN, 14, f"{number:02d} / 13")


def eyebrow(c, text, x, y):
    w = pdfmetrics.stringWidth(text, "NotoM", 8) + 18
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.8)
    c.roundRect(x, y - 5, w, 19, 9, fill=0, stroke=1)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(x + 9, y, text)


def title(c, text, x=MARGIN, y=PAGE_H - 72, size=26, width=PAGE_W - MARGIN * 2):
    return draw_text(c, text, x, y, width, size=size, leading=size * 1.35, font="NotoM", color=TEXT)


def result_box(c, results, x, y, width, height):
    c.setFillColor(SURFACE)
    c.roundRect(x, y, width, height, 9, fill=1, stroke=0)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(x + 18, y + height - 24, "KEY RESULTS")
    yy = y + height - 45
    for result in results:
        c.setFillColor(ACCENT)
        c.circle(x + 20, yy + 3, 2.2, fill=1, stroke=0)
        yy = draw_text(c, result, x + 30, yy, width - 48, size=9, leading=14, max_lines=2) - 3


def case_page(c, number, project, challenge, approach, relevance):
    page_frame(c, number)
    eyebrow(c, project["category_ko"], MARGIN, PAGE_H - 58)
    title(c, project["title_ko"], y=PAGE_H - 92, size=23)
    end = project["period"]["end"] or "진행 중"
    period = f'{project["period"]["start"]} - {end}'
    c.setFont("Noto", 8.5)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 54, period)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 70, project["role"])

    left_x, left_w = MARGIN, 370
    draw_image_cover(c, asset(project["key"]), left_x, 224, left_w, 235)
    result_box(c, project["results"], left_x, 55, left_w, 148)

    right_x, right_w = 444, PAGE_W - 444 - MARGIN
    yy = 448
    for label, body in [("CHALLENGE", challenge), ("APPROACH", approach), ("WHY IT MATTERS", relevance)]:
        c.setFont("NotoM", 8)
        c.setFillColor(ACCENT_DARK)
        c.drawString(right_x, yy, label)
        yy -= 22
        yy = draw_text(c, body, right_x, yy, right_w, size=9.3, leading=15.5)
        yy -= 18
    c.showPage()


def mini_case(c, project, x, y, width, height):
    c.setFillColor(WHITE)
    c.roundRect(x, y, width, height, 10, fill=1, stroke=0)
    draw_image_cover(c, asset(project["key"]), x, y + height - 128, width, 128, radius=10)
    c.setFont("NotoM", 12)
    c.setFillColor(TEXT)
    draw_text(c, project["title_ko"], x + 16, y + height - 151, width - 32, size=11.5, leading=16, font="NotoM", max_lines=2)
    c.setFont("Noto", 7.5)
    c.setFillColor(MUTED)
    c.drawString(x + 16, y + 67, project["role"])
    yy = y + 48
    for item in project["results"][:2]:
        c.setFillColor(ACCENT)
        c.circle(x + 18, yy + 2, 1.8, fill=1, stroke=0)
        draw_text(c, item, x + 27, yy, width - 42, size=8, leading=12, max_lines=1)
        yy -= 17


def build_pdf():
    register_fonts()
    extract_source_assets()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    projects = {project["key"]: project for project in data["projects"]}
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("박종걸 현대자동차 브랜드마케팅 포트폴리오 2026")
    c.setAuthor("Jonggeol Park")

    # 01 Cover
    page_frame(c, 1)
    c.setFillColor(ACCENT)
    c.rect(0, 0, 16, PAGE_H, fill=1, stroke=0)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN, PAGE_H - 57, "HYUNDAI MOTOR · BRAND MARKETING PORTFOLIO · 2026")
    draw_text(c, "콘텐츠로 팬덤을 만들고,\n공간과 상품으로\n브랜드 경험을 확장합니다.", MARGIN, PAGE_H - 125, 500, size=30, leading=44, font="NotoM")
    draw_text(c, "PD의 제작 감각과 마케터의 성과 감각을 함께 갖춘\n브랜드 마케팅·콘텐츠 전략가", MARGIN, 208, 455, size=11, leading=19, color=MUTED)
    c.setFont("NotoM", 17)
    c.setFillColor(TEXT)
    c.drawString(MARGIN, 142, "박종걸")
    c.setFont("Noto", 10)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 122, "Jonggeol Park")
    draw_image_cover(c, asset("portrait"), 592, 98, 205, 390, radius=14)
    c.showPage()

    # 02 Profile
    page_frame(c, 2)
    eyebrow(c, "PROFILE", MARGIN, PAGE_H - 58)
    title(c, "콘텐츠를 만들던 사람이, 브랜드를 키우는 사람이 되었습니다", y=PAGE_H - 98, size=22)
    draw_text(c, "CJ ENM 제작 PD로 시작해 빙그레 콘텐츠전략팀에서 기업 캐릭터 IP, 글로벌 브랜디드 콘텐츠, 팝업스토어를 담당했습니다. 시청자가 머무는 이유를 콘텐츠로 만들고, 그 관계를 공간과 상품으로 확장해 측정 가능한 성과로 연결합니다.", MARGIN, 430, 475, size=10, leading=18)
    c.setFillColor(SURFACE)
    c.roundRect(MARGIN, 78, 480, 310, 12, fill=1, stroke=0)
    c.setFont("NotoM", 9)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN + 22, 360, "EXPERIENCE")
    yy = 330
    for exp in data["experience"]:
        c.setFont("NotoM", 12)
        c.setFillColor(TEXT)
        c.drawString(MARGIN + 22, yy, exp["company"])
        c.setFont("Noto", 8.5)
        c.setFillColor(MUTED)
        c.drawRightString(MARGIN + 458, yy, exp["period"].replace("–", "-"))
        yy = draw_text(c, exp["role"], MARGIN + 22, yy - 20, 430, size=9, leading=14, font="NotoM")
        yy = draw_text(c, exp["summary"], MARGIN + 22, yy - 4, 430, size=8.5, leading=14, color=MUTED) - 22
    right_x = 560
    c.setFont("NotoM", 9)
    c.setFillColor(ACCENT_DARK)
    c.drawString(right_x, 430, "CORE CAPABILITIES")
    capabilities = [
        ("01", "콘텐츠 전략·제작", "예능 PD 기반의 포맷 설계와 제작 품질 관리"),
        ("02", "브랜드 경험", "온라인 세계관을 공간·상품·커머스로 확장"),
        ("03", "글로벌 마케팅", "현지 문화와 알고리즘에 맞춘 콘텐츠 운영"),
        ("04", "데이터·AI 활용", "성과 대시보드와 반복 업무 자동화 도구 직접 개발"),
    ]
    yy = 395
    for num, name, desc in capabilities:
        c.setFont("NotoM", 15)
        c.setFillColor(ACCENT)
        c.drawString(right_x, yy, num)
        c.setFont("NotoM", 11)
        c.setFillColor(TEXT)
        c.drawString(right_x + 40, yy + 1, name)
        draw_text(c, desc, right_x + 40, yy - 17, 220, size=8, leading=13, color=MUTED)
        yy -= 73
    c.showPage()

    # 03 Impact
    page_frame(c, 3)
    eyebrow(c, "IMPACT AT A GLANCE", MARGIN, PAGE_H - 58)
    title(c, "조회수보다 관계를, 캠페인보다 경험의 순환을 설계했습니다", y=PAGE_H - 100, size=23)
    stats = [("5,200만+", "글로벌 콘텐츠 누적 조회"), ("3.2억 원", "팝업 연계 커머스 매출"), ("3.2만 명", "버튜버 채널 신규 구독자"), ("80%+", "글로벌 시리즈 수출국 시청 비중")]
    box_w = 178
    for i, (value, label) in enumerate(stats):
        x = MARGIN + i * (box_w + 16)
        c.setFillColor(SURFACE)
        c.roundRect(x, 350, box_w, 104, 10, fill=1, stroke=0)
        c.setFont("NotoM", 22)
        c.setFillColor(ACCENT_DARK)
        c.drawString(x + 18, 402, value)
        draw_text(c, label, x + 18, 375, box_w - 36, size=8.5, leading=13, color=MUTED)
    columns = [
        ("콘텐츠 → 팬덤", "버추얼 캐릭터와 연속된 세계관으로 재방문할 이유를 만들고, 순 시청자 3,255%·재방문 시청자 3,617% 증가를 달성했습니다."),
        ("팬덤 → 공간", "온라인에서 쌓은 관계를 더현대서울 팝업스토어의 동선·체험·굿즈로 번역해 방문객 3만 3천 명을 만들었습니다."),
        ("공간 → 콘텐츠", "현장에서 생성된 후기 305건이 다시 SNS로 확산되도록 설계해 브랜드 경험이 한 번의 행사가 아닌 순환이 되게 했습니다."),
    ]
    for i, (head, body) in enumerate(columns):
        x = MARGIN + i * 255
        c.setFont("NotoM", 13)
        c.setFillColor(TEXT)
        c.drawString(x, 290, head)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(2)
        c.line(x, 275, x + 44, 275)
        draw_text(c, body, x, 250, 218, size=9.2, leading=16)
    c.showPage()

    case_page(c, 4, projects["banana_salon"], "글로벌 채널의 다음 성장축을 만들면서 제품 노출과 문화적 흥미를 함께 확보해야 했습니다.", "국가별 게스트가 관계 문화를 이야기하는 토크쇼를 설계하고, 제품 경험은 대화의 흐름 안에 배치했습니다. 1-4화 데이터를 기준으로 동남아 타깃 회차를 확대했습니다.", "콘텐츠 공개 이후의 구독 피드 유입까지 설계해 단발 조회가 아닌 반복 시청 기반을 만들었습니다.")
    case_page(c, 5, projects["binggraeus_youtube"], "정보성 콘텐츠 중심 채널은 조회와 참여가 낮았고, 다음 편을 기다릴 이유가 부족했습니다.", "대중화되던 버추얼 유튜버 제작 방식을 기업 캐릭터 IP에 적용했습니다. 테스트 콘텐츠로 가능성을 검증한 뒤 브랜딩, 포맷, 에이전시 운영을 총괄했습니다.", "검증된 트렌드에 브랜드만의 서사를 결합하고, 시청자 행동 지표로 포맷을 개선하는 방식을 체득했습니다.")
    case_page(c, 6, projects["wish_kingdom_popup"], "온라인 팬덤을 일회성 전시가 아닌 몰입형 오프라인 경험으로 전환해야 했습니다.", "SNS 세계관을 공간 동선, 체험, 굿즈, 커머스에 일관되게 적용했습니다. 방문자의 촬영과 공유까지 고객 여정에 포함했습니다.", "브랜드 공간을 메시지를 보여주는 곳이 아니라 소비자가 콘텐츠를 만드는 미디어로 운영했습니다.")
    case_page(c, 7, projects["k_spiciest_cup"], "수출용 바나나맛우유를 글로벌 시청자에게 광고 거부감 없이 각인시켜야 했습니다.", "검증된 매운 음식 챌린지와 제품의 중화 이미지를 결합하고, 국내 인지도보다 해외 팬덤 효율을 기준으로 출연자를 선정했습니다.", "제품의 기능적 장점을 콘텐츠 규칙으로 바꾸고, 수출국 시청 비중으로 타깃 도달을 검증했습니다.")
    case_page(c, 8, projects["hells_gimbap"], "한정된 예산으로 수출용 메로나와 바나나맛우유의 글로벌 도달을 확대해야 했습니다.", "한국 김밥 트렌드, 길거리 인터뷰, 단계별 매운맛 도전을 결합하고 현지 알고리즘 이해도가 높은 크리에이터를 섭외했습니다.", "매체비 없이 2,400만 회를 만든 경험은 포맷·출연자·유통 설계를 하나의 전략으로 보는 기반이 되었습니다.")
    case_page(c, 9, projects["world_war_chef"], "국가별 음식 문화에 대한 관심을 제품 경험과 자연스럽게 연결해야 했습니다.", "각국 셰프의 요리 대결에 메로나 디저트 라운드를 포함해 제품이 포맷의 일부로 기능하도록 구성했습니다.", "문화적 차이를 갈등이 아닌 즐거운 참여 동기로 전환해 수출국 시청자 비중 80%를 확보했습니다.")

    # 10 Social and space
    page_frame(c, 10)
    eyebrow(c, "CONNECTED EXPERIENCES", MARGIN, PAGE_H - 58)
    title(c, "세계관을 채널에서 현실 공간까지 일관되게 확장했습니다", y=PAGE_H - 96, size=22)
    mini_case(c, projects["binggraeus_instagram"], MARGIN, 66, 354, 390)
    mini_case(c, projects["secret_semester"], MARGIN + 378, 66, 354, 390)
    c.showPage()

    # 11 Production foundation
    page_frame(c, 11)
    eyebrow(c, "PRODUCTION FOUNDATION", MARGIN, PAGE_H - 58)
    title(c, "사람과 이야기를 끝까지 완성하는 제작 현장에서 시작했습니다", y=PAGE_H - 96, size=22)
    mini_case(c, projects["mountain_city_women"], MARGIN, 66, 354, 390)
    mini_case(c, projects["shinee"], MARGIN + 378, 66, 354, 390)
    c.showPage()

    # 12 Hyundai fit
    page_frame(c, 12, "HYUNDAI MOTOR · ROLE FIT")
    eyebrow(c, "WHY HYUNDAI", MARGIN, PAGE_H - 58)
    title(c, "현대자동차의 브랜드 철학을 참여하고 공유하는 경험으로 번역하겠습니다", y=PAGE_H - 96, size=22)
    pillars = [
        ("01", "GLOBAL CONTENT", "신차와 콘셉트카의 핵심 가치를 현지 문화와 플랫폼 문법에 맞는 포맷으로 번역합니다.", "수출국 시청자 비중 80% 이상을 확보한 글로벌 시리즈 기획 경험"),
        ("02", "BRAND SPACE", "브랜드 공간을 전시장이 아니라 소비자가 콘텐츠를 만들고 관계를 이어가는 거점으로 설계합니다.", "팝업 방문객 3만 3천 명·대한민국 팝업스토어 어워즈 대상"),
        ("03", "MEASUREMENT & AI", "검색·재방문·구독·전환 지표를 먼저 정의하고, 반복 분석을 자동화해 의사결정 속도를 높입니다.", "광고 성과 대시보드와 콘텐츠 수집·분석 도구 직접 개발"),
    ]
    for i, (num, head, body, evidence) in enumerate(pillars):
        x = MARGIN + i * 255
        c.setFillColor(WHITE)
        c.roundRect(x, 118, 226, 330, 12, fill=1, stroke=0)
        c.setFont("NotoM", 26)
        c.setFillColor(ACCENT)
        c.drawString(x + 18, 400, num)
        c.setFont("NotoM", 9)
        c.setFillColor(ACCENT_DARK)
        c.drawString(x + 18, 366, head)
        draw_text(c, body, x + 18, 325, 190, size=10, leading=18, font="NotoM")
        c.setStrokeColor(LINE)
        c.line(x + 18, 215, x + 208, 215)
        c.setFont("NotoM", 8)
        c.setFillColor(MUTED)
        c.drawString(x + 18, 193, "EVIDENCE")
        draw_text(c, evidence, x + 18, 171, 190, size=8.5, leading=15, color=MUTED)
    c.showPage()

    # 13 Closing
    page_frame(c, 13)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN, PAGE_H - 58, "THANK YOU · 2026")
    draw_text(c, "콘텐츠에서 공간으로,\n공간에서 다시 콘텐츠로.", MARGIN, PAGE_H - 125, 520, size=31, leading=45, font="NotoM")
    draw_text(c, "브랜드 경험의 선순환을 현대자동차와 함께 설계하겠습니다.", MARGIN, 320, 530, size=13, leading=20, color=MUTED)
    c.setFont("NotoM", 18)
    c.setFillColor(TEXT)
    c.drawString(MARGIN, 230, "박종걸 · Jonggeol Park")
    contacts = [("EMAIL", data["contact"]["email"]), ("PORTFOLIO", data["contact"]["portfolio"].replace("https://", "")), ("LINKEDIN", data["contact"]["linkedin"].replace("https://", ""))]
    yy = 187
    for label, value in contacts:
        c.setFont("NotoM", 7.5)
        c.setFillColor(ACCENT_DARK)
        c.drawString(MARGIN, yy, label)
        c.setFont("Noto", 9)
        c.setFillColor(TEXT)
        c.drawString(MARGIN + 78, yy, value)
        yy -= 28
    c.linkURL(data["contact"]["portfolio"], (MARGIN + 78, 145, MARGIN + 400, 164), relative=0)
    c.setFillColor(WHITE)
    c.roundRect(548, 112, 249, 330, 12, fill=1, stroke=0)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(568, 408, "SELECTED RECOGNITION")
    yy = 374
    for award in data["awards"]:
        c.setFont("NotoM", 13)
        c.setFillColor(ACCENT)
        c.drawString(568, yy, award["year"])
        yy = draw_text(c, award["title"], 620, yy, 155, size=9, leading=14, font="NotoM")
        yy = draw_text(c, award["organization"], 620, yy - 2, 155, size=7.5, leading=12, color=MUTED) - 20
    c.showPage()

    c.save()
    print(f"Created {OUTPUT_PDF} ({OUTPUT_PDF.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build_pdf()
