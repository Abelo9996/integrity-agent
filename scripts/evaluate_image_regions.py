"""Run frozen region-localization stress tests, optionally against a saved detector."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

from integrity_agent.detectors import images
from integrity_agent.evaluation import panel
from integrity_agent.evaluation_regions import blot_figure, layout_figure, localized, region_cases


def run(detector, seeds):
    start = time.monotonic()
    results = {
        kind: {"detected": 0, "localized": 0, "total": 0}
        for kind in ("copy", "flip", "contrast", "jpeg", "cross-paper")
    }
    negatives = {
        kind: {"signals": 0, "total": 0}
        for kind in (
            "independent-bands",
            "shared-annotations",
            "table-self",
            "table-pair",
            "plot-self",
            "plot-pair",
        )
    }
    for seed in seeds:
        for case in region_cases(seed):
            m = (
                detector.compare(panel(case.source, "a"), panel(case.target, "b", "other"))
                if case.name == "cross-paper"
                else detector.copy_move(panel(case.target, "b"))
            )
            row = results[case.name]
            row["total"] += 1
            row["detected"] += int(m is not None)
            row["localized"] += int(localized(m, case))
        a, b = blot_figure(seed), blot_figure(seed + 100_000)
        candidates = {
            "independent-bands": detector.copy_move(panel(a, "a")),
            "shared-annotations": detector.compare(panel(a, "a"), panel(b, "b", "other")),
        }
        for kind in ("table", "plot"):
            a, b = layout_figure(seed, kind), layout_figure(seed + 100_000, kind)
            candidates[kind + "-self"] = detector.copy_move(panel(a, "a"))
            candidates[kind + "-pair"] = detector.compare(panel(a, "a"), panel(b, "b", "other"))
        for kind, match in candidates.items():
            negatives[kind]["total"] += 1
            negatives[kind]["signals"] += int(match is not None)
    return {
        "dataset": "procedural small bands and shared typography; not biomedical validation",
        "seeds": list(seeds),
        "positives": results,
        "negatives": negatives,
        "elapsed_seconds": time.monotonic() - start,
        "localization_rule": "At least four correspondence points must lie in both known injected regions; a figure-level flag is insufficient.",
        "caveat": "Fixtures share layout templates; counts do not establish population sensitivity or specificity.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    detector = images
    if args.baseline:
        name = "integrity_agent.detectors.saved_images"
        spec = importlib.util.spec_from_file_location(name, args.baseline)
        detector = importlib.util.module_from_spec(spec)
        sys.modules[name] = detector
        spec.loader.exec_module(detector)
    result = run(detector, range(20, 24) if args.development else range(3000, 3020))
    source = Path(detector.__file__)
    result["detector_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    if not args.baseline:
        result["region_detector_sha256"] = hashlib.sha256(
            Path("src/integrity_agent/detectors/image_regions.py").read_bytes()
        ).hexdigest()
    result["fixtures_sha256"] = hashlib.sha256(
        Path("src/integrity_agent/evaluation_regions.py").read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
