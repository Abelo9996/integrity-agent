"""D5: process context from exact identifier-linked tool inputs."""

from __future__ import annotations

import numpy as np

from ..models import finding


def status(work_id, artifact_id, record):
    updates = record.get("updated-by", [])
    return [
        finding(
            "D5",
            "publication-update",
            "info",
            [work_id],
            [artifact_id],
            f"An identifier-linked {u.get('type', 'update')} notice is recorded for this paper.",
            measurements={
                "notice_doi": u.get("DOI"),
                "type": u.get("type"),
                "source": u.get("source", "publisher"),
            },
            limitations=["Read the official notice; an update is not a finding about an author."],
        )
        for u in updates
        if u.get("type") in ("retraction", "correction", "expression-of-concern", "withdrawal")
    ]


def registry(work_id, paper_artifact, registry_artifact, paper_fields, registry_fields):
    result = []
    for key in ("enrollment", "start_date", "primary_outcome"):
        if (
            key in paper_fields
            and key in registry_fields
            and paper_fields[key] != registry_fields[key]
        ):
            result.append(
                finding(
                    "D5",
                    "registry-difference",
                    "review",
                    [work_id],
                    [paper_artifact, registry_artifact],
                    f"The paper and current registry record differ on {key}.",
                    measurements={
                        "paper": paper_fields[key],
                        "registry": registry_fields[key],
                        "field": key,
                    },
                    limitations=[
                        "Recruitment updates, amendments, analysis populations and terminology may explain differences.",
                        "Current registry text cannot establish historical outcome switching.",
                    ],
                )
            )
    return result


def productivity(work_id, artifact_id, *, year, count, field_counts):
    if len(field_counts) < 20:
        return []
    threshold = float(np.quantile(field_counts, 0.99))
    if count <= threshold:
        return []
    return [
        finding(
            "D5",
            "output-context",
            "info",
            [work_id],
            [artifact_id],
            f"Publication count in {year} exceeds the supplied field sample’s 99th percentile.",
            measurements={
                "year": year,
                "count": count,
                "percentile_99": threshold,
                "baseline_size": len(field_counts),
            },
            limitations=[
                "Field sampling, career stage, collaborations and author disambiguation affect this comparison."
            ],
        )
    ]
