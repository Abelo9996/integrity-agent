"""D6: exact token-shingle overlap across an author's own papers."""

from __future__ import annotations

import re
from itertools import combinations

from ..models import finding


def eligible_sections(sections):
    """Prepare each eligible section once per run."""
    for section in sections:
        tokens = re.findall(r"\b\w+\b", section["text"].lower())
        if len(tokens) >= 40:
            shingles = {tuple(tokens[i : i + 8]) for i in range(len(tokens) - 7)}
            yield section, shingles


def detect(sections):
    return detect_prepared(list(eligible_sections(sections)))


def detect_prepared(prepared):
    result = []
    for (a, sa), (b, sb) in combinations(prepared, 2):
        if a["work_id"] == b["work_id"]:
            continue
        shared = len(sa & sb)
        overlap = shared / min(len(sa), len(sb))
        if overlap < 0.5 or shared < 25:
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
                    "shared_shingles": shared,
                    "context_weight": 2 if important else 1,
                    "sections": [a["section"], b["section"]],
                },
                limitations=[
                    "Methods, attribution, standard terminology and shared cohorts can explain reuse."
                ],
            )
        )
    return result
