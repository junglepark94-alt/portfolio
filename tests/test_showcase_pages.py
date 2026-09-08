import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import showcase_pages  # noqa: E402


DATA_PATH = Path(__file__).parents[1] / "data" / "hyundai_application_2026.json"


def test_load_showcase_content_reads_all_sections_from_the_real_data_file():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    content = showcase_pages.load_showcase_content(data)

    assert len(content["experience_map"]) == 4
    assert content["experience_map"][0]["eyebrow"] == "01 · DOMESTIC BRAND IP"
    assert content["experience_map"][0]["heading"] == "국내 캐릭터 IP 채널"
    assert "목적:" in content["experience_map"][0]["body"]

    assert len(content["working_method"]) == 3
    assert content["working_method"][0]["step"] == "01"
    assert content["working_method"][0]["label"] == "DEFINE"
    assert content["working_method"][0]["evidence"]

    assert content["portfolio_summary"]["organic_subscribers"] == "10만+"
    assert content["production_titles"] == ["산꾼도시여자들", "샤이니의 빛돌기획"]


def test_load_showcase_content_names_the_missing_key():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    del data["working_method"]

    with pytest.raises(KeyError, match="working_method"):
        showcase_pages.load_showcase_content(data)
