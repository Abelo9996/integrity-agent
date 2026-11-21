"""Local, blinded image-review packets and incomplete-label-aware scoring.

Sources and outputs stay outside Git. Human annotations are never manufactured.
"""

from __future__ import annotations

import hashlib
import html
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .detectors.images import compare, copy_move
from .evaluation import panel
from .evaluation_compression import CompressionCase, localized


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_packet(corpus, destination, *, per_article=2, seed=20261121):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Review packet already exists; choose a new destination")
    spec = json.loads(Path(corpus).read_text())
    families = defaultdict(list)
    for row in spec["figures"]:
        families[row["pmcid"]].append(row)
    selected = [
        r
        for key in sorted(families)
        for r in sorted(families[key], key=lambda x: x["source"])[:per_article]
    ]
    if len(families) < 2 or per_article < 1:
        raise ValueError("At least two article families and a positive sample count are required")
    arrays = []
    for row in selected:
        if row["license"].lower().replace("-", " ").strip() not in ("cc by", "cc by 4.0"):
            raise ValueError("Packet accepts explicitly confirmed CC BY sources only")
        if digest(row["path"]) != row["sha256"]:
            raise ValueError("Source digest mismatch")
        with Image.open(row["path"]) as image:
            if image.width * image.height > 40_000_000 or min(image.size) < 128:
                raise ValueError("Source outside image size bounds")
            arrays.append(np.array(image.convert("RGB")))
    cases = []
    for row, a in zip(selected, arrays, strict=True):
        cases.append(dict(kind="unmodified-self", source_ids=[row["id"]], images=[a], truth=None))
        cases.append(
            dict(
                kind="horizontal-flip",
                source_ids=[row["id"]],
                images=[a, np.fliplr(a).copy()],
                truth=2,
            )
        )
        h, w = a.shape[:2]
        side = max(16, min(h, w) // 8)
        # Fixed quadrant-local grid, selected by variance without consulting detectors.
        candidates = [
            (x, y)
            for y in range(h // 8, h // 2 - side, side)
            for x in range(w // 8, w // 2 - side, side)
        ]
        x, y = max(
            candidates, key=lambda xy: float(a[xy[1] : xy[1] + side, xy[0] : xy[0] + side].std())
        )
        tx, ty = 3 * w // 4 - side // 2, 3 * h // 4 - side // 2
        b = a.copy()
        b[ty : ty + side, tx : tx + side] = a[y : y + side, x : x + side]
        if a[y : y + side, x : x + side].std() >= 5:
            cases.append(
                dict(
                    kind="injected-clone",
                    source_ids=[row["id"]],
                    images=[b],
                    truth=3,
                    source_box=[x, y, side, side],
                    target_box=[tx, ty, side, side],
                )
            )
        j = next(j for j, other in enumerate(selected) if other["pmcid"] != row["pmcid"])
        cases.append(
            dict(
                kind="cross-article",
                source_ids=[row["id"], selected[j]["id"]],
                images=[a, arrays[j]],
                truth=None,
            )
        )
    random.Random(seed).shuffle(cases)
    reviewer = destination / "reviewer"
    coordinator = destination / "coordinator"
    (reviewer / "images").mkdir(parents=True)
    coordinator.mkdir()
    index = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Blinded image review</title><style>body{font:16px/1.5 system-ui;max-width:1200px;margin:30px auto}img{max-width:100%}section{border-top:2px solid #777;padding:20px}a{overflow-wrap:anywhere}</style><h1>Blinded image review</h1><p>Assess shared experimental content, not intent. Mark reused labels/axes and disclosed reuse in the rationale. Choose duplicated, distinct, or uncertain; give regions for duplication. Pending is unanswered. Detector predictions and injected labels are withheld. Images may include evaluation transformations; no inference about source authors is justified.</p><p>Edit labels.json locally after inspection; record your reviewer ID and rationale. All source credits are below.</p>'
    ]
    labels, records = [], []
    for number, case in enumerate(cases, 1):
        ident = f"case-{number:03d}"
        index.append(f'<section id="{ident}"><h2>{ident}</h2>')
        paths = []
        for k, pixels in enumerate(case.pop("images")):
            name = f"images/{ident}-{k + 1}.png"
            Image.fromarray(pixels).save(reviewer / name)
            paths.append({"path": name, "sha256": digest(reviewer / name)})
            index.append(
                f'<p>Image {k + 1}</p><a href="{name}"><img src="{name}" alt="{ident} image {k + 1}"></a>'
            )
        index.append(
            "<p>Source credits: "
            + ", ".join(html.escape(x) for x in case["source_ids"])
            + "</p></section>"
        )
        records.append({"case_id": ident, **case, "images": paths})
        labels.append(
            {
                "case_id": ident,
                "label": "pending",
                "reviewer_id": "",
                "rationale": "",
                "regions": [],
            }
        )
    index.append(
        "<h2>Attribution</h2><p>All selected sources are CC BY; evaluation variants are explicitly modified. Original source files remain intact. Case assignments do not assert anomalies in the original publications.</p><ul>"
    )
    for row in selected:
        index.append(
            f'<li>{html.escape(row["id"])} · {html.escape(row.get("citation", ""))} · {html.escape(row["license"])} · <a href="{html.escape(row["source"], quote=True)}">Source figure</a></li>'
        )
    index.append(
        "</ul><p>Anomalies are not proof of misconduct. Findings require expert human review.</p></html>"
    )
    (reviewer / "index.html").write_text("\n".join(index))
    (reviewer / "labels.json").write_text(json.dumps(labels, indent=2) + "\n")
    manifest = {
        "protocol": "native-figures-v1",
        "seed": seed,
        "selected_sources": selected,
        "selection": f"First {per_article} source URLs per article, before detector results; native dimensions; no person selection.",
        "cases": records,
        "expert_review": "pending",
    }
    (coordinator / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def predict_packet(destination, *, compression=False):
    root = Path(destination)
    if (root / "coordinator/predictions.json").exists():
        raise ValueError("Predictions already exist; use a new frozen packet for another detector")
    manifest = json.loads((root / "coordinator/manifest.json").read_text())
    predictions = []
    for case in manifest["cases"]:
        arrays = []
        for item in case["images"]:
            path = root / "reviewer" / item["path"]
            if digest(path) != item["sha256"]:
                raise ValueError("Packet image digest mismatch")
            with Image.open(path) as image:
                arrays.append(np.array(image.convert("RGB")))
        match = (
            copy_move(panel(arrays[0], "a"), compression=compression)
            if len(arrays) == 1
            else compare(
                panel(arrays[0], "a"), panel(arrays[1], "b", "second"), compression=compression
            )
        )
        location = None
        if case["kind"] == "injected-clone":
            location = localized(
                match,
                CompressionCase(
                    "clone",
                    "licensed",
                    arrays[0],
                    arrays[0],
                    tuple(case["source_box"]),
                    tuple(case["target_box"]),
                ),
            )
        predictions.append(
            {
                "case_id": case["case_id"],
                "signal": match is not None,
                "localized": location,
                "finding": match.finding.model_dump(mode="json") if match else None,
            }
        )
    hashes = {
        name: digest(Path(__file__).parent / "detectors" / name)
        for name in ("images.py", "image_regions.py")
    }
    result = {
        "manifest_sha256": digest(root / "coordinator/manifest.json"),
        "image_profile": "experimental-compression" if compression else "standard",
        "detector_sha256": hashes,
        "predictions": predictions,
    }
    (root / "coordinator/predictions.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def score_packet(destination, labels_path=None):
    root = Path(destination)
    manifest_path = root / "coordinator/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    predictions = json.loads((root / "coordinator/predictions.json").read_text())
    if predictions["manifest_sha256"] != digest(manifest_path):
        raise ValueError("Predictions reference a different manifest")
    cases = {c["case_id"]: c for c in manifest["cases"]}
    for case in cases.values():
        for item in case["images"]:
            if digest(root / "reviewer" / item["path"]) != item["sha256"]:
                raise ValueError("Packet image digest mismatch")
    rows = predictions["predictions"]
    if any(
        type(row.get("signal")) is not bool or row.get("localized") not in (None, True, False)
        for row in rows
    ):
        raise ValueError("Predictions require boolean signals")
    if len(rows) != len(cases) or {r["case_id"] for r in rows} != set(cases):
        raise ValueError("Predictions must contain exactly one row per case")
    labels = json.loads(Path(labels_path or root / "reviewer/labels.json").read_text())
    if len(labels) != len(cases) or {r["case_id"] for r in labels} != set(cases):
        raise ValueError("Labels must contain exactly one row per case")
    indexed = {r["case_id"]: r for r in rows}
    counts = Counter()
    confusion = Counter({"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    for row in labels:
        label = row["label"]
        if label not in ("pending", "uncertain", "duplicated", "distinct"):
            raise ValueError("Unknown human label")
        if label != "pending" and (
            not row.get("reviewer_id", "").strip() or not row.get("rationale", "").strip()
        ):
            raise ValueError("Answered labels require reviewer ID and rationale")
        counts[label] += 1
        if label in ("duplicated", "distinct"):
            hit = indexed[row["case_id"]]["signal"]
            confusion[
                ("tp" if hit else "fn") if label == "duplicated" else ("fp" if hit else "tn")
            ] += 1
    generated = {}
    for ident, case in cases.items():
        if case["truth"] is not None:
            bucket = generated.setdefault(case["kind"], {"total": 0, "signals": 0, "localized": 0})
            bucket["total"] += 1
            bucket["signals"] += int(indexed[ident]["signal"])
            bucket["localized"] += int(indexed[ident]["localized"] is True)
    negatives = confusion["fp"] + confusion["tn"]
    return {
        "human_labels": dict(counts),
        "human_labels_complete": counts["pending"] == 0,
        "adjudication_complete": counts["pending"] == 0 and counts["uncertain"] == 0,
        "human_label_confusion": dict(confusion),
        "adjudicated_negative_count": negatives,
        "adjudicated_negative_signal_rate": confusion["fp"] / negatives if negatives else None,
        "generated_manipulations": generated,
        "limitations": "Pending and uncertain labels are excluded, never assumed negative. Adjudicated subsets may be selected and correlated. Reviewer credentials/independence are not authenticated by this tool. Generated-case truth is separate from human review; raw signal presence does not establish correct localization.",
    }
