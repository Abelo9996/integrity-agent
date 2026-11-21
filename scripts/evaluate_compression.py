"""Frozen compression/native-resolution benchmark, with an isolated baseline loader."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from integrity_agent.detectors import images
from integrity_agent.evaluation import panel
from integrity_agent.evaluation_compression import cases, figure, jpeg, localized


def load_baseline(directory):
    name = "integrity_agent.frozen_detectors"
    spec = importlib.util.spec_from_file_location(
        name, directory / "__init__.py", submodule_search_locations=[str(directory)]
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    spec = importlib.util.spec_from_file_location(name + ".images", directory / "images.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name + ".images"] = module
    spec.loader.exec_module(module)
    return module


def run(detector, *, development=False):
    started = time.monotonic()
    seeds = range(60, 63) if development else range(41000, 41008)
    positives = {}
    negatives = {}
    details = []
    for family in ("lanes", "cells"):
        for seed in seeds:
            for c in cases(seed, family, holdout=not development):
                match = detector.copy_move(panel(c.target, "synthetic"))
                key = family + "/" + c.name
                row = positives.setdefault(key, {"signals": 0, "localized": 0, "total": 0})
                row["total"] += 1
                row["signals"] += int(match is not None)
                row["localized"] += int(localized(match, c))
                details.append(
                    {
                        "family": family,
                        "seed": seed,
                        "kind": c.name,
                        "localized": localized(match, c),
                        "finding_id": match.finding.id if match else None,
                    }
                )
            a, _ = figure(seed, family, holdout=not development)
            twin, _ = figure(seed, family, holdout=not development, twins=True)
            b, _ = figure(seed + 100000, family, holdout=not development)
            for kind, match in [
                ("independent", detector.copy_move(panel(a, "a"))),
                ("jpeg-independent", detector.copy_move(panel(jpeg(a, 85), "a"))),
                ("smooth-twins", detector.copy_move(panel(jpeg(twin, 85), "a"))),
                ("shared-labels", detector.compare(panel(a, "a"), panel(b, "b", "other"))),
            ]:
                key = family + "/" + kind
                row = negatives.setdefault(key, {"signals": 0, "total": 0})
                row["total"] += 1
                row["signals"] += int(match is not None)
    return {
        "split": "development" if development else "heldout",
        "seeds": list(seeds),
        "positives": positives,
        "negatives": negatives,
        "details": details,
        "elapsed_seconds": time.monotonic() - started,
        "limitation": "Procedural families, correlated transformations; no biological sensitivity or population false-positive guarantee.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--standard", action="store_true", help="Evaluate the unchanged default profile"
    )
    parser.add_argument("--baseline-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    detector = load_baseline(args.baseline_dir) if args.baseline_dir else images
    if not args.baseline_dir and not args.standard:
        detector = SimpleNamespace(
            __file__=images.__file__,
            compare=partial(images.compare, compression=True),
            copy_move=partial(images.copy_move, compression=True),
        )
    result = run(detector, development=args.development)
    result["profile"] = (
        "standard" if args.standard or args.baseline_dir else "experimental-compression"
    )
    directory = Path(detector.__file__).parent
    result["detector_hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (directory / "images.py", directory / "image_regions.py")
    }
    result["fixture_sha256"] = hashlib.sha256(
        Path("src/integrity_agent/evaluation_compression.py").read_bytes()
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
