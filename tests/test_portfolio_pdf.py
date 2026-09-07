from pathlib import Path

from pypdf import PdfReader


PDF_PATH = Path(
    "C:/Users/user/Documents/Codex/2026-09-07/new-chat/outputs/"
    "박종걸_현대자동차_포트폴리오_2026.pdf"
)


def test_generated_portfolio_pdf_meets_hyundai_upload_requirements():
    assert PDF_PATH.exists()
    assert PDF_PATH.stat().st_size < 2 * 1024 * 1024

    reader = PdfReader(PDF_PATH)
    assert 12 <= len(reader.pages) <= 14
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    for required in [
        "Jonggeol Park",
        "샤이니의 빛돌기획",
        "버추얼",
        "67-82%",
        "현대자동차",
        "web-production-83ee5.up.railway.app",
    ]:
        assert required in text

    for forbidden in [
        "사이니의 빛돌기획",
        "버츄얼",
        "전 세계 버튜버 순위 25위",
        "중동고등학교",
        "바이브코딩",
        "Claude Code · 중",
    ]:
        assert forbidden not in text
