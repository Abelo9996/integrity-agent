"""Runtime assessment ledger; collection or a plan is never proof of a completed check."""

from __future__ import annotations

from collections import Counter

from .models import DetectorCoverage

CHECKS = {
    ("D1", "copy-move"): "No decoded image panels were examined.",
    ("D1", "image-reuse"): "No eligible pair of distinct image artifacts was examined.",
    ("D2", "identical-summary-pair"): "No eligible pair of source-verified mean/SD rows.",
    ("D2", "grim"): "No source-verified rows with confirmed integer-scale assumptions.",
    (
        "D2",
        "grimmer",
    ): "Requires a GRIM-compatible mean, sample SD and confirmed scale assumptions.",
    ("D3", "baseline-dispersion"): "No source-verified randomized baseline supplied by a reviewer.",
    ("D4", "repeated-rows"): "No readable raw-data tables were examined.",
    ("D4", "xlsx-internals"): "No readable XLSX internals were examined.",
    ("D4", "distribution"): "No reviewer-supplied distribution assumptions were examined.",
    ("D5", "publication-status"): "No identifier-linked status records were examined.",
    ("D5", "field-output"): "No field reference with at least 20 observations was examined.",
    ("D5", "registry"): "No quoted paper fields were compared with a linked registry.",
    ("D6", "text-reuse"): "No cross-paper section pairs with at least 40 tokens each.",
}


class AssessmentLedger:
    def __init__(self, work_ids):
        self.work_ids = list(work_ids)
        self.events: list[DetectorCoverage] = []

    def record(self, detector, check, artifacts, *, count=1, detail="", status="ran"):
        for wid in sorted({a.work_id for a in artifacts}):
            self.events.append(
                DetectorCoverage(
                    work_id=wid,
                    detector=detector,
                    check=check,
                    status=status,
                    input_count=count,
                    artifact_ids=sorted({a.artifact_id for a in artifacts if a.work_id == wid}),
                    detail=detail
                    or "Check completed; absence of findings is not evidence of reliability.",
                )
            )

    def run(self, detector, check, artifacts, operation, *, count=1, detail=""):
        try:
            result = operation()
        except Exception as exc:
            self.record(
                detector, check, artifacts, count=count, status="failed", detail=type(exc).__name__
            )
            raise
        self.record(detector, check, artifacts, count=count, detail=detail)
        return result

    def finish(self):
        combined = {}
        for event in self.events:
            key = (event.work_id, event.detector, event.check, event.status, event.detail)
            if key not in combined:
                combined[key] = event.model_copy(deep=True)
            else:
                combined[key].input_count += event.input_count
                combined[key].artifact_ids = sorted(
                    set(combined[key].artifact_ids + event.artifact_ids)
                )
        events = list(combined.values())
        seen = {(e.work_id, e.detector, e.check) for e in self.events}
        return events + [
            DetectorCoverage(
                work_id=wid,
                detector=d,
                check=c,
                status="not_assessed",
                input_count=0,
                detail=reason,
            )
            for wid in self.work_ids
            for (d, c), reason in CHECKS.items()
            if (wid, d, c) not in seen
        ]


def coverage_summary(events):
    return dict(Counter(e.status for e in events))
