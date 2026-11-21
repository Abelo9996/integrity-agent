"""Download explicitly chosen CC BY PMC figures for local benchmark preparation.

Usage: uv run python scripts/prepare_pmc_evaluation.py PMC... [PMC...]
Requires INTEGRITY_CONTACT_EMAIL. Never stages files for Git automatically.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from integrity_agent.acquisition import Collector
from integrity_agent.models import Work
from integrity_agent.transport import Transport


def cc_by(license: str) -> bool:
    normalized = license.lower().replace("_", "-").replace(" ", "-")
    if any(part in normalized for part in ("-nc", "-nd", "-sa")):
        return False
    return bool(re.search(r"(?:cc-?by|creativecommons.org/licenses/by/)", normalized))


def prepare(ids):
    load_dotenv(dotenv_path=Path(".env"))
    http = Transport(Path("cache"), os.getenv("INTEGRITY_CONTACT_EMAIL", ""))
    collector = Collector(http, Path("data/pmc-evaluation"))
    corpus = []
    try:
        for pmcid in ids:
            if not re.fullmatch(r"PMC\d+", pmcid):
                raise ValueError("Expected PMCID identifiers")
            work = Work(
                id=pmcid,
                title="CC BY evaluation source",
                pmcid=pmcid,
                author_id="evaluation-source",
            )
            collector.pmc(work)
        for a in collector.artifacts:
            if not cc_by(a.license) or Path(a.path).suffix.lower() not in (
                ".jpg",
                ".jpeg",
                ".png",
                ".tif",
                ".tiff",
            ):
                continue
            with Image.open(a.path) as img:
                if min(img.size) < 128:
                    continue
            metadata = next(
                (p for p in collector.artifacts if p.artifact_id == a.parent_artifact_id), None
            )
            citation = (
                json.loads(Path(metadata.path).read_text()).get("citation", "") if metadata else ""
            )
            corpus.append(
                {
                    "id": a.artifact_id,
                    "path": a.path,
                    "pmcid": a.linking_identifier,
                    "source": a.url,
                    "sha256": a.sha256,
                    "license": a.license,
                    "citation": citation,
                }
            )
        target = Path("data/pmc-evaluation/corpus.json")
        target.write_text(json.dumps({"figures": corpus, "confirmed_negative_pairs": []}, indent=2))
        print(f"{len(corpus)} eligible images: {target}")
        print(
            "Review images and licenses, label unrelated negative pairs, then run evaluate_pmc_corpus.py."
        )
    finally:
        http.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Supply one or more PMCIDs; no researcher name search is performed.")
    prepare(sys.argv[1:])
