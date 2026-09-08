from pathlib import Path

from pypdf import PdfReader


PDF_PATH = Path(
    "C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/"
    "박종걸_포트폴리오_2026.pdf"
)


def test_generated_portfolio_pdf_is_general_purpose_and_content_rich():
    assert PDF_PATH.exists()
    assert PDF_PATH.stat().st_size < 2 * 1024 * 1024

    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) == 15
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    for required in [
        "Jonggeol Park",
        "고려대학교",
        "TOEIC 990",
        "샤이니의 빛돌기획",
        "버추얼",
        "오가닉 구독자 10만+",
        "국내 캐릭터 IP 채널",
        "글로벌 수출 브랜드 채널",
        "동남아 타깃 회차가 미국 타깃 회차 대비 조회 2.1배",
        "현지 알고리즘만으로 확산",
        "67-82%",
        "jgpark.up.railway.app",
    ]:
        assert required in text

    for forbidden in [
        "사이니의 빛돌기획",
        "버츄얼",
        "HYUNDAI MOTOR",
        "현대자동차와 함께",
        "WHY HYUNDAI",
    ]:
        assert forbidden not in text
