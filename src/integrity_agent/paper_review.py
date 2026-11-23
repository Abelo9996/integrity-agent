"""Per-work navigation derived from accepted claims and the assessment ledger."""

from collections import defaultdict

from .work_types import notice_title

CHECK_LABELS = {
    "D1": "Images",
    "D2": "Stats",
    "D3": "Trial",
    "D4": "Data",
    "D5": "Registry",
    "D6": "Text",
}
QUEUES = {
    "signals": "Review signals",
    "notices": "Publication actions",
    "checked": "Checked, no review signal",
    "missing": "No research-data checks",
    "notice_documents": "Notice documents",
}


def work_review(report: dict) -> dict:
    signals = defaultdict(list)
    notices = defaultdict(list)
    retractions = set()
    checks: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    sources = defaultdict(list)
    for finding in report["findings"]:
        for wid in finding["work_ids"]:
            if finding["tier"] in ("strong", "review"):
                signals[wid].append(finding)
            elif finding["kind"] == "publication-update":
                notices[wid].append(finding)
                if finding["measurements"].get("type") == "retraction":
                    retractions.add(wid)
    for event in report["detector_coverage"]:
        if event["detector"] != "D5" or event["check"] == "registry":
            checks[event["work_id"]][event["detector"]].add(event["status"])
    for artifact in report["artifacts"]:
        sources[artifact["work_id"]].append(artifact)
    rows: dict[str, list[dict]] = {name: [] for name in QUEUES}
    core_checked = set()
    for work in report["works"]:
        wid = work["id"]
        cells = {}
        for detector in CHECK_LABELS:
            statuses = checks[wid][detector]
            if any(f["detector"] == detector for f in signals[wid]):
                cells[detector] = "signal"
            elif {"ran", "failed"} <= statuses:
                cells[detector] = "partial"
            elif "ran" in statuses:
                cells[detector] = "ran"
            elif "failed" in statuses:
                cells[detector] = "failed"
            else:
                cells[detector] = "missing"
        is_notice = notice_title(work["title"])
        has_core = any("ran" in checks[wid][d] for d in ("D1", "D2", "D3", "D4"))
        if has_core:
            core_checked.add(wid)
        if signals[wid]:
            queue = "signals"
        elif notices[wid]:
            queue = "notices"
        elif is_notice:
            queue = "notice_documents"
        elif has_core:
            queue = "checked"
        else:
            queue = "missing"
        rows[queue].append(
            {
                "work_id": wid,
                "cells": cells,
                "notice_title": is_notice,
                "core_checked": has_core,
                "signal_ids": [f["id"] for f in signals[wid]],
                "notice_ids": [f["id"] for f in notices[wid]],
                "artifact_ids": [a["artifact_id"] for a in sources[wid]],
            }
        )
    signal_ids = sorted(wid for wid, items in signals.items() if items)
    action_ids = sorted(wid for wid, items in notices.items() if items)
    total = len(report["works"])
    if signal_ids:
        count = len(signal_ids)
        noun = "record" if count == 1 else "records"
        title = f"Review evidence for {count} publication {noun}."
        subtitle = "Open the review queue to see the strongest evidence first."
    elif not total:
        title, subtitle = (
            "There was nothing to assess.",
            "This run included no publication records.",
        )
    elif retractions and not retractions & core_checked:
        title = "Retraction-linked research remains untested."
        subtitle = (
            f"No review signals on the {len(core_checked)} records with image or data checks."
            if core_checked
            else "No image, statistics, or raw-data checks completed."
        )
    elif not core_checked:
        title, subtitle = (
            "Inconclusive. Research data untested.",
            "No image, statistics, or raw-data checks completed.",
        )
    else:
        title = "No review signals in the checks run."
        subtitle = f"Image or data checks ran on {len(core_checked)} of {total} records."
    return {
        "title": title,
        "explanation": subtitle,
        "queues": rows,
        "core_checked_work_ids": sorted(core_checked),
        "signal_work_ids": signal_ids,
        "publication_action_work_ids": action_ids,
        "retraction_work_ids": sorted(retractions),
        "retraction_work_ids_with_core_checks": sorted(retractions & core_checked),
    }
