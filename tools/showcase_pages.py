# -*- coding: utf-8 -*-
"""Static page renderers for the `showcase` portfolio PDF layout.

The project detail pages come from build_general_portfolio_pdf.Doc.project and are
not touched here. This module only draws the seven hand-laid-out pages around them:
cover, profile, impact, experience map, production foundation, working method, closing.

Editorial copy lives in data/hyundai_application_2026.json, not in this file.
"""

import re

REQUIRED_KEYS = ("portfolio_summary", "experience_map", "working_method",
                 "showcase_production_titles")


def load_showcase_content(data):
    """Pull the showcase-only copy out of the parsed application JSON.

    Raises KeyError naming the first missing top-level key.
    """
    for key in REQUIRED_KEYS:
        if key not in data:
            raise KeyError(key)
    return {
        "portfolio_summary": data["portfolio_summary"],
        "experience_map": data["experience_map"],
        "working_method": data["working_method"],
        "production_titles": data["showcase_production_titles"],
    }


def _norm(title):
    return re.sub(r"\s+", " ", (title or "")).strip()


def split_projects(projects, production_titles):
    """Split scraped projects into detail-page projects and production mini cards.

    Matching is on the whitespace-normalised title. Returns (main, production, missing);
    `production` follows the order given in `production_titles`.
    """
    wanted = [_norm(t) for t in production_titles]
    by_norm = {}
    for p in projects:
        by_norm.setdefault(_norm(p.get("title")), p)

    production, missing = [], []
    for original, key in zip(production_titles, wanted):
        if key in by_norm:
            production.append(by_norm[key])
        else:
            missing.append(original)

    picked = {id(p) for p in production}
    main = [p for p in projects if id(p) not in picked]
    return main, production, missing
