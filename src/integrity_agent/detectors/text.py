"""D6: exact token-shingle overlap across an author's own papers."""

from __future__ import annotations

import re
from itertools import combinations

from ..models import finding


def detect(sections):
    result = []
    for a, b in combinations(sections, 2):
        if a["work_id"] == b["work_id"]:
            continue
        ta, tb = [re.findall(r"\b\w+\b", item["text"].lower()) for item in (a, b)]
        if min(len(ta), len(tb)) < 40:
            continue
        sa, sb = [{tuple(t[i : i + 8]) for i in range(len(t) - 7)} for t in (ta, tb)]
        overlap = len(sa & sb) / min(len(sa), len(sb))
        if overlap < 0.5 or len(sa & sb) < 25:
            continue
        important = any(re.search(r"result|figure|legend", s["section"], re.I) for s in (a, b))
        result.append(
            finding(
                "D6",
                "text-reuse",
                "info",
                [a["work_id"], b["work_id"]],
                [a["artifact_id"], b["artifact_id"]],
                "Long exact token sequences recur across sections of these papers.",
                parameters={"shingle_tokens": 8, "minimum_overlap": 0.5},
                measurements={
                    "overlap": overlap,
                    "shared_shingles": len(sa & sb),
                    "context_weight": 2 if important else 1,
                    "sections": [a["section"], b["section"]],
                },
                limitations=[
                    "Methods, attribution, standard terminology and shared cohorts can explain reuse."
                ],
            )
        )
    return result
