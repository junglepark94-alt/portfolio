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
    "박종걸_포트폴리오_2026.pdf"
)
TOTAL_PAGES = 15

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


def page_frame(c, number, section="BRAND & CONTENT PORTFOLIO"):
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, 27, PAGE_W - MARGIN, 27)
    c.setFont("Noto", 7.5)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 14, f"박종걸 · {section}")
    c.drawRightString(PAGE_W - MARGIN, 14, f"{number:02d} / {TOTAL_PAGES}")


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


def case_page(c, number, project, challenge, insight, execution, takeaway):
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
    sections = [
        ("CHALLENGE", challenge),
        ("INSIGHT & STRATEGY", insight),
        ("EXECUTION", execution),
        ("TAKEAWAY", takeaway),
    ]
    for label, body in sections:
        c.setFont("NotoM", 8)
        c.setFillColor(ACCENT_DARK)
        c.drawString(right_x, yy, label)
        yy -= 18
        yy = draw_text(c, body, right_x, yy, right_w, size=8.45, leading=13.4)
        yy -= 11
    c.showPage()


def card(c, x, y, width, height, heading, body, accent=None):
    c.setFillColor(WHITE)
    c.roundRect(x, y, width, height, 10, fill=1, stroke=0)
    c.setFont("NotoM", 9)
    c.setFillColor(accent or ACCENT_DARK)
    c.drawString(x + 18, y + height - 28, heading)
    draw_text(c, body, x + 18, y + height - 52, width - 36, size=8.7, leading=14.2, color=TEXT)


def mini_case(c, project, x, y, width, height):
    c.setFillColor(WHITE)
    c.roundRect(x, y, width, height, 10, fill=1, stroke=0)
    draw_image_cover(c, asset(project["key"]), x, y + height - 122, width, 122, radius=10)
    c.setFont("NotoM", 12)
    c.setFillColor(TEXT)
    draw_text(c, project["title_ko"], x + 16, y + height - 145, width - 32, size=11.5, leading=16, font="NotoM", max_lines=2)
    c.setFont("Noto", 7.5)
    c.setFillColor(MUTED)
    c.drawString(x + 16, y + 186, project["role"])
    draw_text(c, project["overview"], x + 16, y + 164, width - 32, size=8.1, leading=13, color=MUTED, max_lines=4)
    yy = y + 88
    for item in project["results"][:3]:
        c.setFillColor(ACCENT)
        c.circle(x + 18, yy + 2, 1.8, fill=1, stroke=0)
        draw_text(c, item, x + 27, yy, width - 42, size=8, leading=12, max_lines=1)
        yy -= 17


def build_pdf():
    register_fonts()
    extract_source_assets()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    projects = {project["key"]: project for project in data["projects"]}
    summary = data["portfolio_summary"]
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("박종걸 브랜드 마케팅·콘텐츠 전략 포트폴리오 2026")
    c.setAuthor("Jonggeol Park")

    # 01 Cover
    page_frame(c, 1)
    c.setFillColor(ACCENT)
    c.rect(0, 0, 16, PAGE_H, fill=1, stroke=0)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN, PAGE_H - 57, "BRAND MARKETING · CONTENT STRATEGY · 2026")
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
    draw_text(c, "CJ ENM 제작 PD로 시작해 빙그레 콘텐츠전략팀에서 국내 캐릭터 IP, 글로벌 브랜디드 콘텐츠, 오프라인 브랜드 경험을 담당했습니다. 고객이 머무는 이유를 콘텐츠로 만들고, 그 관계를 공간과 상품으로 확장해 측정 가능한 성과로 연결합니다.", MARGIN, 438, 752, size=9.7, leading=17)
    col_w, gap, base_y, box_h = 240, 16, 63, 318
    c.setFillColor(SURFACE)
    c.roundRect(MARGIN, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("NotoM", 9)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN + 18, base_y + box_h - 28, "EXPERIENCE")
    yy = base_y + box_h - 60
    for exp in data["experience"]:
        c.setFont("NotoM", 12)
        c.setFillColor(TEXT)
        c.drawString(MARGIN + 18, yy, exp["company"])
        c.setFont("Noto", 8.5)
        c.setFillColor(MUTED)
        c.drawRightString(MARGIN + col_w - 18, yy, exp["period"].replace("–", "-"))
        yy = draw_text(c, exp["role"], MARGIN + 18, yy - 20, col_w - 36, size=8.5, leading=13, font="NotoM")
        yy = draw_text(c, exp["summary"], MARGIN + 18, yy - 3, col_w - 36, size=7.7, leading=12.5, color=MUTED, max_lines=4) - 18

    mid_x = MARGIN + col_w + gap
    c.setFillColor(WHITE)
    c.roundRect(mid_x, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("NotoM", 9)
    c.setFillColor(ACCENT_DARK)
    c.drawString(mid_x + 18, base_y + box_h - 28, "EDUCATION & LANGUAGE")
    draw_text(c, "고려대학교 사회학과 · 학사\n2013.03 - 2019.08", mid_x + 18, base_y + box_h - 62, col_w - 36, size=9, leading=15, font="NotoM")
    c.setStrokeColor(LINE)
    c.line(mid_x + 18, base_y + 218, mid_x + col_w - 18, base_y + 218)
    draw_text(c, "OPIc AL · 2025.09\nTOEIC 990 · 2022.03\nTOEIC Speaking 200 · 2022.03", mid_x + 18, base_y + 192, col_w - 36, size=9, leading=20)
    c.setStrokeColor(LINE)
    c.line(mid_x + 18, base_y + 112, mid_x + col_w - 18, base_y + 112)
    draw_text(c, "Premiere Pro · Photoshop\n데이터 분석 · AI 도구 활용", mid_x + 18, base_y + 86, col_w - 36, size=8.7, leading=18)

    right_x = mid_x + col_w + gap
    c.setFillColor(SURFACE)
    c.roundRect(right_x, base_y, col_w, box_h, 12, fill=1, stroke=0)
    c.setFont("NotoM", 9)
    c.setFillColor(ACCENT_DARK)
    c.drawString(right_x + 18, base_y + box_h - 28, "CORE CAPABILITIES")
    capabilities = [
        ("01", "콘텐츠 전략·제작", "예능 PD 기반 포맷 설계와 제작 품질 관리"),
        ("02", "브랜드 경험", "세계관을 공간·상품·커머스로 확장"),
        ("03", "글로벌 마케팅", "현지 문화와 알고리즘에 맞춘 운영"),
        ("04", "데이터·AI 활용", "성과 분석과 반복 업무 도구화"),
    ]
    yy = base_y + box_h - 65
    for num, name, desc in capabilities:
        c.setFont("NotoM", 15)
        c.setFillColor(ACCENT)
        c.drawString(right_x + 18, yy, num)
        c.setFont("NotoM", 11)
        c.setFillColor(TEXT)
        c.drawString(right_x + 58, yy + 1, name)
        draw_text(c, desc, right_x + 58, yy - 17, col_w - 76, size=7.8, leading=12.5, color=MUTED)
        yy -= 66
    c.showPage()

    # 03 Impact
    page_frame(c, 3)
    eyebrow(c, "IMPACT AT A GLANCE", MARGIN, PAGE_H - 58)
    title(c, "서로 다른 채널에서 관계를 만들고, 브랜드 경험으로 확장했습니다", y=PAGE_H - 100, size=23)
    stats = [
        (f"오가닉 구독자 {summary['organic_subscribers']}", "국내·글로벌 채널 합산"),
        (summary["global_content_views"], "글로벌 콘텐츠 누적 조회"),
        (summary["popup_commerce_revenue"], "팝업 연계 커머스 매출"),
        (summary["export_market_viewer_share"], "글로벌 시리즈 수출국 시청 비중"),
    ]
    box_w = 178
    for i, (value, label) in enumerate(stats):
        x = MARGIN + i * (box_w + 16)
        c.setFillColor(SURFACE)
        c.roundRect(x, 350, box_w, 104, 10, fill=1, stroke=0)
        c.setFont("NotoM", 16 if i == 0 else 22)
        c.setFillColor(ACCENT_DARK)
        c.drawString(x + 18, 402, value)
        draw_text(c, label, x + 18, 375, box_w - 36, size=8.5, leading=13, color=MUTED)
    columns = [
        ("국내 캐릭터 IP 채널", "빙그레우스를 버추얼 유튜버로 전환해 검색·순 시청자·재방문·재생률을 함께 성장시키고 팬덤 기반을 만들었습니다."),
        ("글로벌 수출 브랜드 채널", "국가별 문화 코드와 현지 알고리즘에 맞는 시리즈를 설계해 제품 인지도와 오가닉 구독자를 함께 확보했습니다."),
        ("온라인 → 오프라인", "온라인 세계관을 공간·굿즈·커머스로 확장하고, 현장의 콘텐츠가 다시 SNS로 돌아오는 순환을 설계했습니다."),
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

    # 04 Experience map
    page_frame(c, 4)
    eyebrow(c, "EXPERIENCE MAP", MARGIN, PAGE_H - 58)
    title(c, "채널의 목적과 고객에 따라 다른 성장 공식을 설계했습니다", y=PAGE_H - 96, size=22)
    map_cards = [
        ("01 · DOMESTIC BRAND IP", "국내 캐릭터 IP 채널", "목적: 검색과 재방문을 통한 팬덤 형성\n방식: 버추얼 캐릭터·연속 세계관·제품 스토리텔링\n성과: 순 시청자 3,255%·재방문 3,617% 증가"),
        ("02 · GLOBAL BRAND CHANNEL", "글로벌 수출 브랜드 채널", "목적: 국가별 제품 인지도와 오가닉 구독자 확보\n방식: 현지 문화 코드·크리에이터·플랫폼 알고리즘\n성과: 콘텐츠 5,200만+ 조회·수출국 시청 비중 80%+"),
        ("03 · BRAND EXPERIENCE", "오프라인 브랜드 경험", "목적: 온라인 팬덤을 체험·상품·커머스로 확장\n방식: 세계관 기반 공간·동선·MD·공유 장치 통합\n성과: 방문객 3.3만 명·연계 매출 3.2억 원"),
        ("04 · PRODUCTION", "방송·브랜디드 콘텐츠 제작", "목적: 출연자의 매력과 프로그램 기대감 극대화\n방식: 기획·촬영·편집·티저·예고·후반 관리\n경험: Mnet·tvN 음악·푸드·야외 버라이어티"),
    ]
    coords = [(MARGIN, 274), (MARGIN + 378, 274), (MARGIN, 73), (MARGIN + 378, 73)]
    for (ey, head, body), (x, y) in zip(map_cards, coords):
        c.setFillColor(WHITE)
        c.roundRect(x, y, 354, 178, 11, fill=1, stroke=0)
        c.setFont("NotoM", 7.5)
        c.setFillColor(ACCENT_DARK)
        c.drawString(x + 18, y + 147, ey)
        c.setFont("NotoM", 13)
        c.setFillColor(TEXT)
        c.drawString(x + 18, y + 116, head)
        draw_text(c, body, x + 18, y + 87, 318, size=8.7, leading=16, color=MUTED)
    c.showPage()

    case_page(c, 5, projects["banana_salon"],
              "챌린지·요리 대결을 잇는 글로벌 채널의 다음 성장축을 만들면서 제품 노출과 문화적 흥미를 함께 확보해야 했습니다.",
              "국가별 관계 문화를 대화 소재로 삼는 '교양 있는 크로스컬처 예능'을 설정했습니다. 제품 소개가 아닌 재미있는 토크로 유입시킨 뒤 제품을 만나게 하는 순서를 설계했습니다.",
              "모모랜드 낸시와 국가별 아이돌·유튜버·틱톡커를 섭외하고 현지어 자막을 적용했습니다. 제품 코너는 1분 숏츠로 분리 유통했습니다. 동남아 타깃 회차가 미국 타깃 회차 대비 조회 2.1배·참여율 2.2배를 기록했습니다.",
              "오가닉 유입의 67-82%가 구독 피드에서 발생했습니다. 타깃 국가의 구독자를 확보하면 다음 콘텐츠가 반복 도달하는 구조를 확인하고, 포맷을 Melona Salon으로 확장했습니다.")
    case_page(c, 6, projects["binggraeus_youtube"],
              "정보성 콘텐츠 중심의 국내 기업 브랜드 채널은 인스타그램 대비 조회와 참여가 낮았고, 시청자가 다음 편을 기다릴 이유가 부족했습니다.",
              "버추얼 유튜버 기술의 대중화와 Unity 기반 제작 비용의 하락을 기회로 보고, 빙그레우스를 기업형 버튜버로 전환하는 포맷을 기획·제안했습니다.",
              "소규모 테스트로 가능성을 검증한 뒤 채널 브랜딩, 연속 세계관, 콘텐츠 포맷, 에이전시 선정과 운영을 총괄했습니다. 검색·순 시청자·재방문·재생률을 함께 관리했습니다.",
              "트렌드를 따라가는 데서 끝나지 않고 브랜드가 그 포맷을 써야 하는 이유를 설계했습니다. 국내 기업 최초 사례로 YouTube Works 2개 부문 Finalist와 소셜아이어워드 대상을 받았습니다.")
    case_page(c, 7, projects["binggraeus_instagram"],
              "3년간 이어진 빙그레 왕국 세계관을 유지하면서도 실제 제품과 판매 공간의 연결성을 높여 신규 유입의 거리감을 낮춰야 했습니다.",
              "빙그레 제품이 판매되는 장소를 세계관으로 끌어온 시즌4 '슈퍼 빙그레'를 기획했습니다. 기존 팬에게는 연속성을, 신규 고객에게는 익숙한 구매 맥락을 제공했습니다.",
              "연간 운영 계획과 채널 리뉴얼을 담당하고 신제품·주력제품 콘텐츠 100건을 발행했습니다. 제품을 PPL이 아닌 에피소드의 주요 스토리텔링 소재로 활용했습니다.",
              "팔로워를 17만 명에서 21만 명으로 성장시키고 제품 콘텐츠 평균 도달 15만 회를 달성했습니다. 2024 소셜아이어워드 통합대상으로 이어졌습니다.")
    case_page(c, 8, projects["wish_kingdom_popup"],
              "온라인에서 형성된 빙그레우스 팬덤을 일회성 전시가 아닌 몰입형 오프라인 브랜드 경험으로 확장해야 했습니다.",
              "SNS에서 쌓아온 세계관과 스토리텔링을 공간 동선, 체험, 굿즈, 커머스까지 일관되게 번역했습니다. 방문자의 촬영과 공유도 고객 여정에 포함했습니다.",
              "콘셉트와 공간 구성, 체험 요소, MD, 현장 운영, 네이버 쇼핑라이브 연계를 통합 기획했습니다. 현장에서 생성된 콘텐츠가 다시 SNS로 확산되는 구조를 설계했습니다.",
              "방문객 3.3만 명, 굿즈 8,544건, 연계 매출 3.2억 원, 자발적 후기 305건을 기록했고 2025 대한민국 팝업스토어 어워즈 대상을 받았습니다.")
    case_page(c, 9, projects["secret_semester"],
              "7월 성수기에 1020 소비자의 참여를 끌어내면서 제품·브랜드 인지도와 MD 판매를 동시에 높여야 했습니다.",
              "1학기와 2학기 사이 여름방학이라는 타깃의 생활 맥락에 착안해 '빙그레 왕국에서 비밀스럽게 열리는 특별한 학기'라는 콘셉트를 만들었습니다.",
              "부스 콘셉트, 체험 콘텐츠, MD 기획·제작, 온·오프라인 홍보, 현장 운영을 총괄해 캐릭터 라이선싱 페어와 서울일러스트레이션페어에 적용했습니다.",
              "주최 측 추산 최다 방문객, 일 평균 매출 500만 원, MD 전 물량 소진을 기록했습니다. 짧은 행사에서도 타깃 맥락과 세계관의 결합이 몰입을 만든다는 점을 검증했습니다.")
    case_page(c, 10, projects["k_spiciest_cup"],
              "수출용 바나나맛우유를 글로벌 시청자에게 광고 거부감 없이 각인시키고, 한정된 예산으로 실제 수출국 도달을 확보해야 했습니다.",
              "글로벌 스테디 트렌드인 매운 음식 챌린지와 제품의 중화 이미지를 결합해 '매운 음식 후 바나나맛우유'라는 반복 가능한 소구 공식을 만들었습니다.",
              "국내 인지도보다 해외 팬덤 효율을 기준으로 K-pop 출연자를 선정하고 14편의 시리즈를 기획·운영했습니다. 제품의 기능적 장점을 콘텐츠 규칙 안에 배치했습니다.",
              "1,300만 조회, 26만 인터랙션, 순 구독자 1.1만 명을 확보했습니다. 전체 시청자의 82%가 수출국에서 발생해 타깃 도달의 질까지 검증했습니다.")
    case_page(c, 11, projects["hells_gimbap"],
              "별도 매체비 없이 수출용 메로나와 바나나맛우유의 글로벌 도달을 확대하려면 포맷·출연자·유통을 하나의 전략으로 설계해야 했습니다.",
              "글로벌에서 주목받던 한국 김밥과 길거리 챌린지를 결합했습니다. 단계별 매운맛을 버티는 과정에서 제품이 자연스러운 중화 아이템으로 기능하게 했습니다.",
              "미국 숏폼 시장에서 인지도가 높은 크리에이터 @iamfromkorea를 섭외하고, 본편 5편과 숏츠 25편을 플랫폼 문법에 맞게 배포했습니다. 현지 알고리즘만으로 확산되었습니다.",
              "매체 집행 없이 2,400만 조회와 84만 인터랙션, 순 구독자 4.1만 명을 만들었습니다. 단일 영상은 덴마크·말레이시아에서 1,700만 회를 기록했습니다.")
    case_page(c, 12, projects["world_war_chef"],
              "국가별 음식 문화에 대한 높은 관심을 갈등이 아닌 즐거운 참여 동기로 바꾸고, 메로나 제품 경험과 자연스럽게 연결해야 했습니다.",
              "각국 셰프가 같은 요리를 자국 스타일로 해석하는 경쟁심을 유입 구조로 삼고, 메로나를 활용한 자국 디저트 대결을 별도 라운드로 설계했습니다.",
              "10편의 시리즈에서 요리 대결, MC·게스트 평가, 메로나 디저트 라운드가 반복되는 포맷을 구축해 제품이 광고가 아니라 프로그램의 규칙으로 기능하게 했습니다.",
              "940만 조회, 8만 인터랙션, 순 구독자 1.2만 명을 확보했습니다. 전체 시청자의 80%가 수출국에서 발생해 문화 기반 포맷의 타깃 적합성을 입증했습니다.")

    # 13 Production foundation
    page_frame(c, 13)
    eyebrow(c, "PRODUCTION FOUNDATION", MARGIN, PAGE_H - 58)
    title(c, "사람과 이야기를 끝까지 완성하는 제작 현장에서 시작했습니다", y=PAGE_H - 96, size=22)
    mini_case(c, projects["mountain_city_women"], MARGIN, 66, 354, 390)
    mini_case(c, projects["shinee"], MARGIN + 378, 66, 354, 390)
    c.showPage()

    # 14 How I work
    page_frame(c, 14, "HOW I WORK")
    eyebrow(c, "WORKING METHOD", MARGIN, PAGE_H - 58)
    title(c, "감각으로 시작하되, 고객 행동과 데이터로 끝까지 검증합니다", y=PAGE_H - 96, size=22)
    pillars = [
        ("01", "DEFINE", "조회수보다 먼저 고객 행동과 성공 지표를 정의합니다. 검색·재방문·구독·타깃 국가 비중·현장 참여를 목적에 맞게 선택합니다.", "국내 IP 채널과 글로벌 채널에 서로 다른 KPI 적용"),
        ("02", "DESIGN & DELIVER", "인사이트를 포맷, 출연자, 유통, 공간, 상품까지 연결하고 유관부서와 에이전시를 하나의 실행 기준으로 정렬합니다.", "PD 제작 경험 + 브랜드 캠페인 총괄 경험"),
        ("03", "MEASURE & TOOL", "공개 후 데이터를 다음 기획에 반영하고 반복 업무는 도구화합니다. 광고 성과 대시보드와 콘텐츠 수집 자동화 도구를 직접 구현했습니다.", "분석 속도 향상·사내 뉴스레터 작성 시간 70% 단축"),
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

    # 15 Closing
    page_frame(c, 15)
    c.setFont("NotoM", 8)
    c.setFillColor(ACCENT_DARK)
    c.drawString(MARGIN, PAGE_H - 58, "THANK YOU · 2026")
    draw_text(c, "콘텐츠에서 공간으로,\n공간에서 다시 콘텐츠로.", MARGIN, PAGE_H - 125, 520, size=31, leading=45, font="NotoM")
    draw_text(c, "사람이 머물고, 참여하고, 다시 찾는 브랜드 경험을 설계합니다.", MARGIN, 320, 530, size=13, leading=20, color=MUTED)
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
