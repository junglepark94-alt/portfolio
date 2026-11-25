import json

from app import Profile, db


def _login(client):
    with client.session_transaction() as sess:
        sess["logged_in"] = True


def test_profile_form_rows_are_parsed_into_json_lists(client, portfolio_app):
    _login(client)
    form = {
        "exp_company": [" 빙그레 ", "", "CJ ENM"],
        "exp_period": ["2022.03 – 현재", "버려짐", "2018.01 – 2021.12"],
        "exp_role": ["콘텐츠 전략", "", "PD"],
        "exp_bullets": ["- 기획\n\n운영 ", "", "제작"],
        "en_exp_company": ["Binggrae"],
        "en_exp_period": ["2022.03 – Present"],
        "en_exp_role": ["Content Strategy"],
        "en_exp_bullets": ["Planning\nOps"],
        "edu_school": ["서울대", " "],
        "edu_major": ["경영", "x"],
        "edu_degree": ["학사", "x"],
        "edu_period": ["2010 – 2014", "x"],
        "en_edu_school": ["SNU"],
        "en_edu_major": ["Business"],
        "en_edu_degree": ["BA"],
        "en_edu_period": ["2010 – 2014"],
        "award_title": ["대상", "우수상"],
        "award_org": ["팝업 어워즈"],          # 두 번째 행은 기관이 비어 있다
        "award_year": ["2025", "2024"],
        "en_award_title": ["Grand Prize"],
        "en_award_org": ["Pop-Up Awards"],
        "en_award_year": ["2025"],
        "tool_name": ["Figma", "", "Python"],
        "tool_level": ["상", "중", "중"],
        "en_tool_name": ["Figma"],
        "en_tool_level": ["Advanced"],
        "lang_exam": ["TOEIC", ""],
        "lang_score": ["950", "x"],
        "lang_date": ["2024.05", "x"],
    }
    resp = client.post("/admin/profile", data=form)
    assert resp.status_code == 302

    with portfolio_app.app_context():
        p = db.session.get(Profile, 1)
        assert json.loads(p.experience_json) == [
            {"company": "빙그레", "period": "2022.03 – 현재", "role": "콘텐츠 전략",
             "bullets": ["- 기획", "운영"]},
            {"company": "CJ ENM", "period": "2018.01 – 2021.12", "role": "PD", "bullets": ["제작"]},
        ]
        assert json.loads(p.experience_en_json) == [
            {"company": "Binggrae", "period": "2022.03 – Present", "role": "Content Strategy",
             "bullets": ["Planning", "Ops"]},
        ]
        assert json.loads(p.education_json) == [
            {"school": "서울대", "major": "경영", "degree": "학사", "period": "2010 – 2014"},
        ]
        assert json.loads(p.education_en_json) == [
            {"school": "SNU", "major": "Business", "degree": "BA", "period": "2010 – 2014"},
        ]
        assert json.loads(p.awards_json) == [
            {"title": "대상", "org": "팝업 어워즈", "year": "2025"},
            {"title": "우수상", "org": "", "year": "2024"},
        ]
        assert json.loads(p.awards_en_json) == [
            {"title": "Grand Prize", "org": "Pop-Up Awards", "year": "2025"},
        ]
        assert json.loads(p.tools_json) == [
            {"name": "Figma", "level": "상"}, {"name": "Python", "level": "중"},
        ]
        assert json.loads(p.tools_en_json) == [{"name": "Figma", "level": "Advanced"}]
        assert json.loads(p.language_scores_json) == [
            {"exam": "TOEIC", "score": "950", "date": "2024.05"},
        ]


def test_profile_form_with_no_rows_stores_empty_lists(client, portfolio_app):
    _login(client)
    assert client.post("/admin/profile", data={}).status_code == 302
    with portfolio_app.app_context():
        p = db.session.get(Profile, 1)
        for attr in ("experience_json", "experience_en_json", "education_json", "education_en_json",
                     "awards_json", "awards_en_json", "tools_json", "tools_en_json",
                     "language_scores_json"):
            assert getattr(p, attr) == "[]", attr
