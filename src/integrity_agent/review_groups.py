"""Conservative presentation grouping of already-verified image evidence."""

from __future__ import annotations

import json

from .models import stable_id


def review_groups(findings, artifacts):
    known = {a.artifact_id: a for a in artifacts}
    grouped = {}
    for f in findings:
        key = f.id
        if f.detector == "D1" and f.evidence_files:
            # Same bytes, work associations, parameters, measurements and overlay.
            # Distinct encodings/regions remain separate; provenance is never erased.
            key = json.dumps(
                {
                    "detector": f.detector,
                    "kind": f.kind,
                    "tier": f.tier,
                    "sources": sorted((known[a].work_id, known[a].sha256) for a in f.artifact_ids),
                    "parameters": f.parameters,
                    "measurements": {
                        k: v
                        for k, v in f.measurements.items()
                        if k not in ("panel_id", "panel_ids")
                    },
                    "evidence": sorted(f.evidence_sha256.values()),
                    "limitations": f.limitations,
                },
                sort_keys=True,
            )
        grouped.setdefault(key, []).append(f)
    return [
        {
            "id": stable_id("group", [f.id for f in members]),
            "representative_id": members[0].id,
            "finding_ids": [f.id for f in members],
            "artifact_ids": sorted({a for f in members for a in f.artifact_ids}),
            "work_ids": sorted({w for f in members for w in f.work_ids}),
        }
        for members in grouped.values()
    ]
