"""Index exact detector inputs and their document parents for file-level review."""

from collections import defaultdict
from pathlib import Path


def file_review(report: dict) -> dict:
    works = {work["id"] for work in report["works"]}
    artifacts = {a["artifact_id"]: a for a in report["artifacts"]}
    checks = defaultdict(set)
    for event in report["detector_coverage"]:
        if event["status"] != "ran" or (event["detector"] == "D5" and event["check"] != "registry"):
            continue
        for aid in event["artifact_ids"]:
            artifact = artifacts.get(aid)
            if artifact and artifact["work_id"] == event["work_id"] and event["work_id"] in works:
                checks[aid].add(event["detector"])

    def file_group(aid):
        artifact = artifacts[aid]
        parent = artifacts.get(artifact["parent_artifact_id"])
        if (
            parent
            and parent["work_id"] == artifact["work_id"]
            and Path(parent["path"]).suffix.lower() == ".pdf"
            and artifact["relation"].startswith("native PDF embedded image ")
        ):
            return parent["artifact_id"]
        return aid

    groups = defaultdict(list)
    for aid in sorted(checks):
        groups[file_group(aid)].append(aid)
    flagged = defaultdict(list)
    signal_groups = []
    by_id = {f["id"]: f for f in report["findings"]}
    for f in report["findings"]:
        if f["tier"] in ("review", "strong"):
            for aid in f["artifact_ids"]:
                flagged[aid].append(f["id"])
    for group in report["review_groups"]:
        if by_id[group["representative_id"]]["tier"] in ("review", "strong"):
            signal_groups.append(group["representative_id"])
    return {
        "signal_group_ids": signal_groups,
        "flagged_files": [
            {"artifact_id": aid, "finding_ids": sorted(set(ids))}
            for aid, ids in sorted(flagged.items())
        ],
        "checked_files": [
            {
                "file_id": parent,
                "input_ids": aids,
                "detectors": sorted({detector for aid in aids for detector in checks[aid]}),
                "flagged_input_ids": sorted(set(aids) & flagged.keys()),
            }
            for parent, aids in sorted(groups.items())
        ],
    }
