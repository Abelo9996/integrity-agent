"""Evaluate manually curated, licensed source images and confirmed negative pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.stats import beta

from integrity_agent.detectors.images import compare, copy_move
from integrity_agent.evaluation import manipulations, panel
from integrity_agent.evaluation_regions import RegionCase, localized


def run(manifest, output=Path("outputs/pmc-evaluation")):
    spec = json.loads(Path(manifest).read_text())
    if not spec.get("confirmed_negative_pairs"):
        raise ValueError(
            "Label confirmed unrelated pairs before evaluation; different filenames alone are insufficient"
        )
    figures = {}
    for item in spec["figures"]:
        path = Path(item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Source image hash mismatch")
        with Image.open(path) as image:
            # Standardized panel crop is explicit; originals remain intact with their provenance.
            a = np.array(image.convert("L"))
        h, w = a.shape
        side = min(h, w)
        square = a[(h - side) // 2 : (h + side) // 2, (w - side) // 2 : (w + side) // 2]
        figures[item["id"]] = cv2.resize(square, (320, 320), interpolation=cv2.INTER_AREA)
    confusion = {str(i): {str(j): 0 for j in (0, 1, 2, 3)} for i in (0, 1, 2, 3)}
    copy_hits = 0
    clone_localized = 0
    unmodified_signals = sum(copy_move(panel(a, ident)) is not None for ident, a in figures.items())
    for ident, a in figures.items():
        for kind, (label, b) in manipulations(a).items():
            match = compare(panel(a, ident), panel(b, ident + "-" + kind, "manipulated"))
            prediction = match.finding.measurements["category"] if match else 0
            confusion[str(label)][str(prediction)] += 1
            if kind == "cloned-regions":
                clone_match = copy_move(panel(b, ident + "-clone"))
                copy_hits += int(clone_match is not None)
                clone_localized += int(
                    localized(
                        clone_match, RegionCase(kind, a, b, (30, 30, 90, 90), (180, 180, 90, 90))
                    )
                )
    pairs = {tuple(sorted(pair)) for pair in spec["confirmed_negative_pairs"]}
    if any(len(pair) != 2 or pair[0] == pair[1] for pair in pairs):
        raise ValueError("Negative pairs must contain two distinct image IDs")
    for first, second in sorted(pairs):
        match = compare(panel(figures[first], first), panel(figures[second], second, "negative"))
        confusion["0"][str(match.finding.measurements["category"] if match else 0)] += 1
    per_category = {}
    for label in ("1", "2", "3"):
        total = sum(confusion[label].values())
        predicted = sum(row[label] for row in confusion.values())
        per_category[label] = {
            "detection_recall": 1 - confusion[label]["0"] / total,
            "classification_recall": confusion[label][label] / total,
            "classification_precision": confusion[label][label] / predicted if predicted else None,
        }
    negatives = sum(confusion["0"].values())
    false_positives = negatives - confusion["0"]["0"]
    result = {
        "source_manifest": str(manifest),
        "source_count": len(figures),
        "categories": per_category,
        "confusion_actual_by_predicted": confusion,
        "negative_pairs": negatives,
        "false_positives": false_positives,
        "negative_pair_fpr_95pct_upper": float(
            beta.ppf(0.975, false_positives + 1, negatives - false_positives)
        )
        if false_positives < negatives
        else 1.0,
        "interval_note": "Descriptive binomial bound only; shared source images make pairs dependent.",
        "negative_review": spec.get("negative_review", {}),
        "unmodified_copy_move_signals": unmodified_signals,
        "unmodified_images": len(figures),
        "false_positive_rate": 1 - confusion["0"]["0"] / negatives,
        "copy_move_recall": copy_hits / len(figures),
        "copy_move_localization_recall": clone_localized / len(figures),
        "copy_move_metric_note": "copy_move_recall is legacy any-signal recall; localization requires four correspondences in both injected regions.",
        "normalization": "central square crop resized to 320px",
    }
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    (target / "metrics.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/pmc-evaluation"))
    args = parser.parse_args()
    run(args.manifest, args.output)
