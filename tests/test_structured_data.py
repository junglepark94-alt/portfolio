import json
import re


def _ld(html):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m, "JSON-LD block missing"
    return json.loads(m.group(1))


def test_korean_page_exposes_person_and_projects_as_json_ld(client):
    data = _ld(client.get("/").get_data(as_text=True))

    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "ProfilePage"
    person = data["mainEntity"]
    assert person["@type"] == "Person"
    assert person["name"] == "박종걸"
    assert person["jobTitle"] == "브랜드 마케팅 · 콘텐츠 전략"
    works = data["hasPart"]
    assert works and works[0]["@type"] == "CreativeWork"
    assert "Banana Salon" in works[0]["name"]
    assert "67–82%" in works[0]["description"]


def test_english_page_json_ld_uses_english_copy(client):
    data = _ld(client.get("/en").get_data(as_text=True))

    assert data["inLanguage"] == "en"
    assert data["mainEntity"]["name"] == "Jonggeol Park"
    assert data["hasPart"][0]["name"].startswith("Banana Salon")


def test_json_ld_cannot_break_out_of_its_script_tag(portfolio_app):
    from app import Profile, db

    with portfolio_app.app_context():
        db.session.get(Profile, 1).tagline = "</script><script>alert(1)</script>"
        db.session.commit()
    html = portfolio_app.test_client().get("/").get_data(as_text=True)
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    assert "<script>" not in block
    json.loads(block)


def test_about_subsections_use_h3_under_the_h2(client):
    html = client.get("/").get_data(as_text=True)
    about = html.split('id="about"', 1)[1].split("<section", 1)[0]
    assert '<h4 class="about-block-title"' not in about
