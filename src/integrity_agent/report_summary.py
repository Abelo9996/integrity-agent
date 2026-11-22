"""Plain-language counts derived only from verified results and recorded coverage.

These aggregates do not create findings, change tiers, or deduplicate independent
events. Every result category retains all supporting finding/artifact references.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import Artifact, Coverage, DetectorCoverage, Finding, Work, stable_id

DETECTORS = {
    "D1": "Images",
    "D2": "Summary statistics",
    "D3": "Trial baseline statistics",
    "D4": "Raw data and spreadsheets",
    "D5": "Publication status and context",
    "D6": "Text overlap",
}
TIERS = {"strong": "Strong signal", "review": "Needs review", "info": "Information only"}
TIER_ORDER = {"strong": 0, "review": 1, "info": 2}
KINDS = {
    "publication-update": (
        "Publication notices",
        "Read the linked notices. Several sources may record the same update; these counts are not independent issues or a judgment about the author.",
    ),
    "output-context": (
        "Publication output context",
        "Output is compared with a supplied field sample. Career stage, collaboration and author matching can affect the comparison.",
    ),
    "text-reuse": (
        "Text overlap",
        "Repeated wording needs context: attribution, standard language and shared sources can explain it.",
    ),
    "image-reuse": (
        "Image similarities",
        "Inspect the matched regions and captions for attribution, shared controls and versions of the same work.",
    ),
    "copy-move": (
        "Repeated regions within images",
        "Inspect the marked regions. Similar structures or graphics can also produce matches.",
    ),
    "registry-difference": (
        "Trial registry differences",
        "Compare the paper with dated registry versions; updates and analysis populations may explain differences.",
    ),
}


def notice_title(title: str) -> bool:
    """A title cue only, never proof of a document's type or retraction status."""
    return bool(
        re.match(
            r"^\s*(?:retraction|correction|erratum|corrigendum|withdrawal)"
            r"(?:\s+note)?\s*(?::|\bto\b|\bof\b|$)",
            title,
            re.IGNORECASE,
        )
    )


def reading_summary(
    works: list[Work],
    artifacts: list[Artifact],
    findings: list[Finding],
    coverage: list[Coverage],
    checks: list[DetectorCoverage],
) -> dict:
    """Call only after reference and file verification, with accepted findings."""
    known = {w.id: w for w in works}
    categories: dict[tuple[str, str, str], list[Finding]] = {}
    for f in findings:
        categories.setdefault((f.detector, f.kind, f.tier), []).append(f)
    rows = []
    for (detector, kind, tier), members in sorted(
        categories.items(),
        key=lambda pair: (
            TIER_ORDER[pair[0][2]],
            pair[0][1] == "output-context",
            pair[0][0],
            pair[0][1],
        ),
    ):
        label, explanation = KINDS.get(
            kind,
            (
                kind.replace("-", " ").capitalize(),
                "Review the detector assumptions and source evidence.",
            ),
        )
        row = {
            "id": stable_id("category", (detector, kind, tier)),
            "detector": detector,
            "kind": kind,
            "tier": tier,
            "label": label,
            "explanation": explanation,
            "result_count": len(members),
            "finding_ids": sorted(f.id for f in members),
            "artifact_ids": sorted({a for f in members for a in f.artifact_ids}),
            "work_ids": sorted({w for f in members for w in f.work_ids}),
        }
        if kind == "text-reuse":
            row["notice_title_finding_ids"] = sorted(
                f.id
                for f in members
                if all(wid in known and notice_title(known[wid].title) for wid in f.work_ids)
            )
        if kind == "publication-update":
            row["status_work_ids"] = {
                status: sorted(
                    {w for f in members if f.measurements.get("type") == status for w in f.work_ids}
                )
                for status in ("retraction", "correction", "expression-of-concern", "withdrawal")
                if any(f.measurements.get("type") == status for f in members)
            }
        rows.append(row)

    coverage_rows = []
    for detector, label in DETECTORS.items():
        events = [c for c in checks if c.detector == detector and c.work_id in known]
        ran = sorted({c.work_id for c in events if c.status == "ran"})
        failed = sorted({c.work_id for c in events if c.status == "failed"})
        coverage_rows.append(
            {
                "detector": detector,
                "label": label,
                "works_with_completed_check": len(ran),
                "work_ids_with_completed_check": ran,
                "work_ids_with_failed_check": failed,
                "works_without_completed_check": len(known) - len(ran),
                "total_work_records": len(known),
                "status": "some_checks_ran" if ran else "failed" if failed else "not_assessed",
            }
        )
    missing_core = [
        row["label"] for row in coverage_rows[:4] if not row["works_with_completed_check"]
    ]
    if len(missing_core) == 4:
        headline = "Image and numerical checks could not be assessed."
    elif missing_core:
        headline = "Some image or numerical checks could not be assessed."
    else:
        headline = "Read the results alongside the coverage limits."
    priority = [f for f in findings if f.tier in ("review", "strong")]
    return {
        "headline": headline,
        "missing_core_checks": missing_core,
        "counts_by_tier": {tier: sum(f.tier == tier for f in findings) for tier in TIERS},
        "priority_finding_ids": sorted(f.id for f in priority),
        "priority_artifact_ids": sorted({a for f in priority for a in f.artifact_ids}),
        "priority_work_ids": sorted({w for f in priority for w in f.work_ids}),
        "categories": rows,
        "detector_coverage": coverage_rows,
        "collection_attempts": dict(Counter(c.status for c in coverage if c.work_id in known)),
        "artifact_formats": dict(Counter(a.media_type or "unspecified" for a in artifacts)),
        "counting_note": "Counts refer to tool results and linked work records, not independent issues or confirmed problems.",
    }
