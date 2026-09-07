import json
import os

import pytest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import GalleryItem, Profile, Project, app, db  # noqa: E402


@pytest.fixture()
def portfolio_app():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        profile = Profile(
            id=1,
            name="박종걸",
            name_en="Jonggeol Park",
            role="브랜드 마케팅 · 콘텐츠 전략",
            role_en="Brand Marketing · Content Strategy",
            tagline="콘텐츠에서 팬덤을 만들고, 공간과 상품으로 브랜드 경험을 확장합니다.",
            tagline_en="I build fandom through content and extend it into memorable brand experiences.",
            about_text="소개",
            about_text_en="Profile",
            experience_json="[]",
            experience_en_json="[]",
            education_json="[]",
            education_en_json="[]",
            awards_json="[]",
            awards_en_json="[]",
        )
        project = Project(
            title="글로벌 브랜디드 콘텐츠 ‘Banana Salon’",
            title_en="Banana Salon — Global Branded Talk Show",
            description="오가닉 유입 중 구독 피드 비중 67–82%",
            description_en="Subscriber feeds generated 67–82% of organic traffic.",
            detail_text="진행 중인 글로벌 토크쇼",
            detail_text_en="An ongoing global talk-show series.",
            kpi="오가닉 유입 중 구독 피드 비중 67–82%",
            kpi_en="Subscriber feeds: 67–82% of organic traffic",
            my_role="기획·운영 총괄",
            my_role_en="Strategy and production lead",
            category="콘텐츠 기획",
            category_en="Content Strategy & Production",
            period="2026.07 – 진행 중",
            order=1,
            links_json=json.dumps([], ensure_ascii=False),
            links_en_json=json.dumps([], ensure_ascii=False),
        )
        gallery = GalleryItem(
            title="현장 기록",
            title_en="On-site work",
            image_filename="placeholder.jpg",
            sort_order=1,
        )
        db.session.add_all([profile, project, gallery])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(portfolio_app):
    return portfolio_app.test_client()

