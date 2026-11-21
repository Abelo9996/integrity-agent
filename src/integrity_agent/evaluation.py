"""Reproducible procedural smoke benchmark; not a biomedical validation dataset."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.stats import beta

from .detectors.images import Panel, compare, copy_move


def synthetic_image(seed: int, size=320):
    rng = np.random.default_rng(seed)
    noise = rng.normal(125, 35, (size, size)).clip(0, 255).astype(np.uint8)
    a = cv2.GaussianBlur(noise, (3, 3), 0.6)
    for _ in range(85):
        x, y = rng.integers(12, size - 12, 2)
        radius = int(rng.integers(3, 15))
        cv2.circle(a, (int(x), int(y)), radius, int(rng.integers(20, 235)), -1)
        cv2.circle(a, (int(x), int(y)), max(1, radius // 3), int(rng.integers(20, 235)), -1)
    return a


def manipulations(a):
    clone = a.copy()
    clone[180:270, 180:270] = a[30:120, 30:120]
    altered = a.copy()
    altered[70:130, 120:180] = 110
    return {
        "duplicate": (1, a.copy()),
        "crop": (2, a[35:275, 30:280].copy()),
        "rotate": (2, np.rot90(a).copy()),
        "flip": (2, np.fliplr(a).copy()),
        "scale": (2, cv2.resize(a, None, fx=0.7, fy=0.7)),
        "contrast": (2, np.clip(a.astype(float) * 0.65 + 35, 0, 255).astype(np.uint8)),
        "cloned-regions": (3, clone),
        "edited-features": (3, altered),
    }


def panel(a, name, work="synthetic-work"):
    return Panel(id=name, work_id=work, artifact_id=name, pixels=a)


def evaluate(root: Path, *, seeds=12):
    root.mkdir(parents=True, exist_ok=True)
    counts = {str(i): {"tp": 0, "fn": 0} for i in (1, 2, 3)}
    details = {}
    clone_hits = 0
    confusion = {str(i): {str(j): 0 for j in (0, 1, 2, 3)} for i in (0, 1, 2, 3)}
    for seed in range(1000, 1000 + seeds):
        a = synthetic_image(seed)
        for kind, (category, b) in manipulations(a).items():
            match = compare(
                panel(a, f"base-{seed}"), panel(b, f"{kind}-{seed}", "synthetic-second")
            )
            hit = match is not None
            predicted = match.finding.measurements["category"] if match else 0
            confusion[str(category)][str(predicted)] += 1
            counts[str(category)]["tp" if hit else "fn"] += 1
            details.setdefault(kind, {"hits": 0, "total": 0})
            details[kind]["hits"] += int(hit)
            details[kind]["total"] += 1
            if kind == "cloned-regions":
                clone_hits += int(copy_move(panel(b, f"clone-{seed}")) is not None)
    fp = 0
    negative_count = seeds * 5
    copy_fp = 0
    for i in range(negative_count):
        a, b = synthetic_image(5000 + i), synthetic_image(9000 + i)
        match = compare(panel(a, "negative-a"), panel(b, "negative-b", "other-work"))
        fp += int(match is not None)
        confusion["0"][str(match.finding.measurements["category"] if match else 0)] += 1
        copy_fp += int(copy_move(panel(a, "negative-self")) is not None)
    metrics = {}
    for category, c in counts.items():
        metrics[category] = {**c, "recall": c["tp"] / (c["tp"] + c["fn"])}
    classification = {}
    for label in ("1", "2", "3"):
        tp = confusion[label][label]
        predicted = sum(row[label] for row in confusion.values())
        actual = sum(confusion[label].values())
        classification[label] = {
            "precision": tp / predicted if predicted else 0,
            "recall": tp / actual if actual else 0,
            "correct": tp,
            "predicted": predicted,
            "actual": actual,
        }
    result = {
        "dataset": "procedural textured figures, seeds 1000+; no biomedical generalization",
        "categories": metrics,
        "classification": classification,
        "confusion_actual_by_predicted": confusion,
        "manipulations": details,
        "false_positives": fp,
        "negative_pairs": negative_count,
        "false_positive_rate": fp / negative_count,
        "false_positive_rate_95pct_upper": float(beta.ppf(0.975, fp + 1, negative_count - fp))
        if fp < negative_count
        else 1,
        "precision_at_benchmark_mix": sum(c["tp"] for c in counts.values())
        / (sum(c["tp"] for c in counts.values()) + fp),
        "copy_move_recall": clone_hits / seeds,
        "copy_move_false_positives": copy_fp,
        "copy_move_negative_images": negative_count,
        "interpretation": "Categories label injected manipulations. Reuse detection is not correct classification of edits. No claim of clinical sensitivity.",
    }
    (root / "metrics.json").write_text(json.dumps(result, indent=2))
    return result


def save_demo_images(root):
    root.mkdir(parents=True, exist_ok=True)
    a = synthetic_image(71)
    paths = []
    for name, pixels in [("original", a), ("flipped", np.fliplr(a).copy())]:
        path = root / f"{name}.png"
        Image.fromarray(pixels).save(path)
        paths.append(path)
    return paths
