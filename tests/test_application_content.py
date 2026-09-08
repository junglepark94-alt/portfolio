import json
from pathlib import Path


CONTENT_PATH = Path(__file__).parents[1] / "data" / "hyundai_application_2026.json"


def load_content():
    return json.loads(CONTENT_PATH.read_text(encoding="utf-8"))


def test_canonical_content_has_consistent_identity_and_application_limits():
    content = load_content()

    assert content["identity"] == {
        "name_ko": "박종걸",
        "name_en": "Jonggeol Park",
    }
    assert content["application"]["position"] == "브랜드마케팅/디자인 및 아트기획"
    assert len(content["application"]["essays"]) == 2
    assert all(len(essay["answer"]) <= 1000 for essay in content["application"]["essays"])


def test_canonical_projects_use_normalized_facts_and_terminology():
    content = load_content()
    serialized = json.dumps(content, ensure_ascii=False)

    assert "사이니" not in serialized
    assert "버츄얼" not in serialized
    assert "런칭" not in serialized
    assert "컨셉카" not in serialized
    assert "전 세계 버튜버 순위 25위" not in serialized

    projects = {project["key"]: project for project in content["projects"]}
    assert projects["shinee"]["institution"] == "(주)CJ ENM"
    assert projects["banana_salon"]["institution"] == "(주)빙그레"
    assert projects["banana_salon"]["status"] == "진행 중"
    assert projects["banana_salon"]["period"]["end"] is None


def test_portfolio_summary_distinguishes_the_channels_behind_aggregate_growth():
    content = load_content()
    summary = content["portfolio_summary"]

    assert summary["organic_subscribers"] == "10만+"
    assert summary["organic_subscriber_scope"] == [
        "국내 캐릭터 IP 채널",
        "글로벌 수출 브랜드 채널",
    ]

