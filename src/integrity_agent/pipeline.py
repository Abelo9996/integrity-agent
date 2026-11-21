"""Orchestrate collection/extraction, pure detectors, evidence writes and verification."""

from __future__ import annotations

import hashlib
import json
import platform
import re
from importlib.metadata import version
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from . import extraction
from .acquisition import Collector
from .agent import AnthropicProvider, plan
from .assessment import AssessmentLedger
from .detectors import images, process, raw, stats, text
from .models import Baseline, Coverage, Stat, finding
from .report import write_report
from .repositories import jats_assets, linked_repository, trials

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def analyze(
    collector: Collector,
    author,
    works,
    output: Path,
    *,
    llm=False,
    review_input=None,
    network=True,
    provider=None,
    experimental_compression=False,
):
    provider = provider or (AnthropicProvider() if llm else None)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evidence").mkdir(exist_ok=True)
    by_work = {w.id: w for w in works}
    artifacts = collector.artifacts
    sections, panels, findings = [], [], []
    ledger = AssessmentLedger(by_work)

    def summarize(rows):
        result = stats.detect_summary(rows)
        for row in rows:
            source = [a for a in artifacts if a.artifact_id == row.artifact_id]
            if row.integer_scale_confirmed:
                ledger.record("D2", "grim", source)
                k = row.items if row.scale == "average" else 1
                if row.sd is not None and stats.grim(row.mean, row.n, k):
                    value = stats.grimmer(row.mean, row.sd, row.n, k)
                    ledger.record(
                        "D2",
                        "grimmer",
                        source,
                        status="not_assessed" if value is None else "ran",
                        detail="Computation cap reached."
                        if value is None
                        else "Necessary lattice check only.",
                    )
        for a, b in combinations(rows, 2):
            if (
                a.sd
                and b.sd
                and (a.work_id, a.group, a.variable) != (b.work_id, b.group, b.variable)
            ):
                ledger.record(
                    "D2",
                    "identical-summary-pair",
                    [x for x in artifacts if x.artifact_id in (a.artifact_id, b.artifact_id)],
                )
        return result

    extracted_stats = []
    whole_figure_matches = []
    captions = {}
    texts = {}
    # Safe archive expansion with artifact-level derivation provenance.
    for a in list(artifacts):
        p = Path(a.path)
        if p.suffix in (".zip", ".gz", ".tar"):
            try:
                for name, content in extraction.archive_members(p.read_bytes()):
                    collector.save(
                        by_work[a.work_id],
                        content,
                        a.source,
                        a.url + "#" + name,
                        a.linking_identifier,
                        a.license,
                        Path(name).suffix,
                        parent=a,
                        relation="archive member " + name,
                    )
            except Exception as exc:
                collector.coverage.append(
                    Coverage(
                        work_id=a.work_id,
                        source="archive",
                        status="failed",
                        detail=type(exc).__name__,
                    )
                )
    for a in list(artifacts):
        p = Path(a.path)
        if p.suffix == ".xml":
            try:
                parsed = extraction.jats(p.read_bytes())
            except Exception as exc:
                for detector in ("D2", "D6"):
                    ledger.record(
                        detector, "input-decoding", [a], status="failed", detail=type(exc).__name__
                    )
                collector.coverage.append(
                    Coverage(
                        work_id=a.work_id, source="jats", status="failed", detail=type(exc).__name__
                    )
                )
                continue
            texts[a.artifact_id] = parsed["text"]
            extracted_stats.extend(
                extraction.table_stats(parsed["tables"], a.work_id, a.artifact_id)
            )
            captions.setdefault(a.work_id, {}).update(parsed["captions"])
            sections.extend(
                {
                    "work_id": a.work_id,
                    "artifact_id": a.artifact_id,
                    "section": title,
                    "text": content,
                }
                for title, content in parsed["sections"]
            )
            (output / f"tables-{a.artifact_id}.json").write_text(
                json.dumps(parsed["tables"], indent=2)
            )
            if network:
                if a.source not in ("pmc", "europe-pmc"):
                    collector.attempt(
                        by_work[a.work_id],
                        "JATS assets",
                        lambda a=a: jats_assets(collector, by_work[a.work_id], a),
                    )
                for link in parsed["data_links"]:
                    collector.attempt(
                        by_work[a.work_id],
                        "linked-repository",
                        lambda link=link, a=a: linked_repository(
                            collector, by_work[a.work_id], a, link
                        ),
                    )
                collector.attempt(
                    by_work[a.work_id],
                    "clinicaltrials",
                    lambda a=a, parsed=parsed: trials(
                        collector, by_work[a.work_id], a, parsed["text"]
                    ),
                )
        if p.suffix == ".pdf":
            try:
                extracted, source_text = extraction.pdf_images(p.read_bytes())
                texts[a.artifact_id] = source_text
                if provider:
                    try:
                        extraction_result = provider.extract_pdf(
                            {
                                "work_id": a.work_id,
                                "artifact_id": a.artifact_id,
                                "source_text": source_text[:100_000],
                            }
                        )
                        good, bad = extraction.validate_pdf_stats(
                            extraction_result.rows, source_text, a.work_id, a.artifact_id
                        )
                        extracted_stats.extend(good)
                        (output / f"pdf-extraction-rejections-{a.artifact_id}.json").write_text(
                            json.dumps(bad, indent=2)
                        )
                        collector.coverage.append(
                            Coverage(
                                work_id=a.work_id,
                                source="PDF structured extraction",
                                status="ok",
                                detail=f"{len(good)} source-verified rows; {len(bad)} rejected; text limit 100000 characters",
                            )
                        )
                    except Exception as exc:
                        ledger.record(
                            "D2",
                            "PDF-structured-extraction",
                            [a],
                            status="failed",
                            detail=type(exc).__name__,
                        )
                        collector.coverage.append(
                            Coverage(
                                work_id=a.work_id,
                                source="PDF structured extraction",
                                status="failed",
                                detail=type(exc).__name__,
                            )
                        )
                sections.append(
                    {
                        "work_id": a.work_id,
                        "artifact_id": a.artifact_id,
                        "section": "PDF unclassified",
                        "text": source_text,
                    }
                )
                for name, content in extracted:
                    collector.save(
                        by_work[a.work_id],
                        content,
                        a.source,
                        a.url + "#" + name,
                        a.linking_identifier,
                        a.license,
                        Path(name).suffix,
                        parent=a,
                        relation="native PDF embedded image " + name,
                    )
                collector.coverage.append(
                    Coverage(
                        work_id=a.work_id,
                        source="PDF tables",
                        status="skipped",
                        detail="Supply verified structured review input; unverified numeric extraction is not analyzed.",
                    )
                )
            except Exception as exc:
                for detector in ("D1", "D2", "D6"):
                    ledger.record(
                        detector, "PDF-decoding", [a], status="failed", detail=type(exc).__name__
                    )
                collector.coverage.append(
                    Coverage(
                        work_id=a.work_id,
                        source="PDF extraction",
                        status="failed",
                        detail=type(exc).__name__,
                    )
                )
    # Expand repository archives discovered after JATS parsing (one bounded level).
    expanded_parents = {
        a.parent_artifact_id for a in artifacts if a.relation.startswith("archive member")
    }
    for a in list(artifacts):
        if Path(a.path).suffix in (".zip", ".gz", ".tar") and a.artifact_id not in expanded_parents:
            try:
                for name, content in extraction.archive_members(Path(a.path).read_bytes()):
                    collector.save(
                        by_work[a.work_id],
                        content,
                        a.source,
                        a.url + "#" + name,
                        a.linking_identifier,
                        a.license,
                        Path(name).suffix,
                        parent=a,
                        relation="archive member " + name,
                    )
            except Exception as exc:
                collector.coverage.append(
                    Coverage(
                        work_id=a.work_id,
                        source="repository archive",
                        status="failed",
                        detail=type(exc).__name__,
                    )
                )
    detector_plan = plan(artifacts)
    for a in list(artifacts):
        p = Path(a.path)
        try:
            if p.suffix.lower() in IMAGE_SUFFIXES:
                with Image.open(p) as image:
                    if image.width * image.height > 40_000_000:
                        raise ValueError("Image pixel limit exceeded")
                    pixels = np.array(image.convert("RGB"))
                caption = next(
                    (value for key, value in captions.get(a.work_id, {}).items() if key in a.url),
                    "",
                )
                segments = extraction.split_panels(pixels)
                if len(segments) > 1:
                    cm = ledger.run(
                        "D1",
                        "copy-move",
                        [a],
                        lambda a=a, pixels=pixels, caption=caption: images.copy_move(
                            images.Panel(
                                a.artifact_id + "-whole", a.work_id, a.artifact_id, pixels, caption
                            ),
                            compression=experimental_compression,
                        ),
                    )
                    if cm:
                        whole_figure_matches.append(cm)
                for i, (x, y, w, h, pix) in enumerate(segments):
                    panels.append(
                        images.Panel(
                            a.artifact_id + f"-panel-{i}",
                            a.work_id,
                            a.artifact_id,
                            pix,
                            caption,
                            (x, y, w, h),
                        )
                    )
            if p.suffix in (".csv", ".tsv"):
                frame = pd.read_csv(p, sep="\t" if p.suffix == ".tsv" else ",")
                findings.extend(
                    ledger.run(
                        "D4",
                        "repeated-rows",
                        [a],
                        lambda a=a, frame=frame: raw.rows(frame, a.work_id, a.artifact_id),
                        count=len(frame),
                        detail="Three-row nonconstant sequences; tables too short cannot yield a repeated sequence.",
                    )
                )
            if p.suffix == ".xlsx":
                findings.extend(
                    ledger.run(
                        "D4",
                        "xlsx-internals",
                        [a],
                        lambda a=a, p=p: raw.workbook(p.read_bytes(), a.work_id, a.artifact_id),
                    )
                )
                for frame in pd.read_excel(p, sheet_name=None).values():
                    findings.extend(
                        ledger.run(
                            "D4",
                            "repeated-rows",
                            [a],
                            lambda a=a, frame=frame: raw.rows(frame, a.work_id, a.artifact_id),
                            count=len(frame),
                            detail="Three-row nonconstant sequences; tables too short cannot yield a repeated sequence.",
                        )
                    )
            if a.source == "crossref" and p.suffix == ".json":
                findings.extend(
                    ledger.run(
                        "D5",
                        "publication-status",
                        [a],
                        lambda a=a, p=p: process.status(
                            a.work_id, a.artifact_id, json.loads(p.read_text())["message"]
                        ),
                    )
                )
            if a.source == "openalex-baseline":
                record = json.loads(p.read_text())
                for year, count in record["author_counts"].items():
                    eligible = len(record["years"][str(year)]) >= 20
                    findings.extend(
                        process.productivity(
                            a.work_id,
                            a.artifact_id,
                            year=int(year),
                            count=count,
                            field_counts=record["years"][str(year)],
                        )
                    )
                    ledger.record(
                        "D5",
                        "field-output",
                        [a],
                        status="ran" if eligible else "not_assessed",
                        detail=f"Year {year}: field sample has {len(record['years'][str(year)])} observations.",
                    )
            if a.source == "retraction-watch":
                record = json.loads(p.read_text())
                ledger.record("D5", "publication-status", [a])
                findings.append(
                    finding(
                        "D5",
                        "publication-update",
                        "info",
                        [a.work_id],
                        [a.artifact_id],
                        "An exact DOI match appears in Crossref’s Retraction Watch dataset.",
                        measurements={
                            "type": record.get("RetractionNature", "").lower(),
                            "notice_doi": record.get("RetractionDOI"),
                        },
                        limitations=[
                            "Read the official notice; this context does not establish responsibility or intent."
                        ],
                    )
                )
        except Exception as exc:
            detector = (
                "D1"
                if p.suffix.lower() in IMAGE_SUFFIXES
                else "D4"
                if p.suffix in (".csv", ".tsv", ".xlsx")
                else "D5"
            )
            ledger.record(
                detector, "input-decoding", [a], status="failed", detail=type(exc).__name__
            )
            collector.coverage.append(
                Coverage(
                    work_id=a.work_id,
                    source="extraction",
                    status="failed",
                    detail=type(exc).__name__,
                )
            )
    matches = []
    if detector_plan["D1"]:
        try:
            matches = images.detect(panels, compression=experimental_compression)
        except Exception as exc:
            ledger.record("D1", "copy-move", panels, status="failed", detail=type(exc).__name__)
            ledger.record("D1", "image-reuse", panels, status="failed", detail=type(exc).__name__)
        else:
            for panel in panels:
                ledger.record(
                    "D1",
                    "copy-move",
                    [panel],
                    detail="Decoded panel examined with bounded feature/component search.",
                )
            for first, second in combinations(panels, 2):
                if first.artifact_id != second.artifact_id:
                    ledger.record(
                        "D1",
                        "image-reuse",
                        [first, second],
                        detail="Panel pair examined; content gates can exclude smooth or sparse imagery.",
                    )
    matches += whole_figure_matches
    for match in matches:
        filename = "evidence/" + match.finding.id + ".png"
        Image.fromarray(match.evidence).save(output / filename)
        match.finding.evidence_files.append(filename)
        with (output / filename).open("rb") as evidence:
            match.finding.evidence_sha256[filename] = hashlib.file_digest(
                evidence, "sha256"
            ).hexdigest()
        findings.append(match.finding)
    if detector_plan["D6"]:
        findings.extend(text.detect(sections))
        for first, second in combinations(sections, 2):
            if (
                first["work_id"] != second["work_id"]
                and min(len(re.findall(r"\b\w+\b", x["text"])) for x in (first, second)) >= 40
            ):
                ledger.record(
                    "D6",
                    "text-reuse",
                    [
                        a
                        for a in artifacts
                        if a.artifact_id in (first["artifact_id"], second["artifact_id"])
                    ],
                )
    findings.extend(summarize(extracted_stats))
    (output / "extracted-stats.json").write_text(
        json.dumps([s.model_dump(mode="json") for s in extracted_stats], indent=2)
    )
    if review_input:
        spec = json.loads(Path(review_input).read_text())
        checked_stats = []
        for item in spec.get("stats", []):
            s = Stat.model_validate(item)
            a = next(
                (a for a in artifacts if a.artifact_id == s.artifact_id and a.work_id == s.work_id),
                None,
            )
            if a and extraction.numbers_verified(s, texts.get(s.artifact_id, "")):
                checked_stats.append(s)
            else:
                collector.coverage.append(
                    Coverage(
                        work_id=s.work_id,
                        source="stat validation",
                        status="skipped",
                        detail="Unverified source numbers or artifact association",
                    )
                )
        findings.extend(summarize(checked_stats))
        for item in spec.get("registry", []):
            paper = next((a for a in artifacts if a.artifact_id == item["paper_artifact_id"]), None)
            record = next(
                (
                    a
                    for a in artifacts
                    if a.artifact_id == item["registry_artifact_id"]
                    and a.source == "clinicaltrials"
                ),
                None,
            )
            if not paper or not record or paper.work_id != record.work_id:
                raise ValueError("Registry comparison artifact mismatch")
            source_text = texts.get(paper.artifact_id, "")
            fields = item["paper_fields"]
            quote = item.get("source_quote", "")
            if (
                not quote
                or quote not in source_text
                or any(str(v) not in quote for v in fields.values())
            ):
                raise ValueError("Registry paper fields lack a verbatim source quote")
            protocol = json.loads(Path(record.path).read_text())["protocolSection"]
            expected = {}
            enrollment = protocol.get("designModule", {}).get("enrollmentInfo", {}).get("count")
            if enrollment is not None:
                expected["enrollment"] = enrollment
            start = protocol.get("statusModule", {}).get("startDateStruct", {}).get("date")
            if start:
                expected["start_date"] = start
            primary = protocol.get("outcomesModule", {}).get("primaryOutcomes", [])
            if primary:
                expected["primary_outcome"] = "; ".join(p["measure"] for p in primary)
            common = set(fields) & set(expected) & {"enrollment", "start_date", "primary_outcome"}
            ledger.record(
                "D5",
                "registry",
                [paper, record],
                count=len(common),
                status="ran" if common else "not_assessed",
                detail="Only shared fields are compared with the current registry version.",
            )
            findings.extend(
                process.registry(
                    paper.work_id, paper.artifact_id, record.artifact_id, fields, expected
                )
            )
        for item in spec.get("distributions", []):
            artifact = next((a for a in artifacts if a.artifact_id == item["artifact_id"]), None)
            if not artifact:
                raise ValueError("Unknown distribution artifact")
            path = Path(artifact.path)
            frame = (
                pd.read_excel(path, sheet_name=item.get("sheet", 0))
                if path.suffix == ".xlsx"
                else pd.read_csv(path, sep="\t" if path.suffix == ".tsv" else ",")
            )
            options = {
                key: item[key]
                for key in ("expected_skew", "terminal_digits", "hard_cap", "digit_resolution")
                if key in item
            }
            values = pd.to_numeric(frame[item["column"]], errors="coerce")
            finite_count = int(np.isfinite(values).sum())
            enabled = bool(
                options.get("expected_skew")
                or options.get("terminal_digits")
                or options.get("hard_cap") is not None
            )
            ledger.record(
                "D4",
                "distribution",
                [artifact],
                count=finite_count,
                status="ran" if finite_count >= 100 and enabled else "not_assessed",
                detail=f"Requires >=100 finite values and explicit assumptions; supplied options: {sorted(options)}.",
            )
            findings.extend(
                raw.distribution(
                    pd.to_numeric(frame[item["column"]], errors="coerce"),
                    artifact.work_id,
                    artifact.artifact_id,
                    column=item["column"],
                    **options,
                )
            )
        for item in spec.get("baselines", []):
            table = Baseline.model_validate(item)
            if not any(
                a.artifact_id == table.artifact_id and a.work_id == table.work_id for a in artifacts
            ):
                raise ValueError("Baseline work/artifact mismatch")
            if table.artifact_id not in texts:
                raise ValueError("Baseline has no extracted source text")
            from decimal import Decimal

            tokens = {
                Decimal(t)
                for t in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", texts[table.artifact_id])
            }
            values = [v for row in table.means + table.sds for v in row] + table.ns
            if not all(Decimal(str(v)) in tokens for v in values):
                raise ValueError("Baseline contains numbers absent from source")
            findings.extend(stats.baseline_dispersion(table))
            ledger.record(
                "D3",
                "baseline-dispersion",
                [a for a in artifacts if a.artifact_id == table.artifact_id],
                status="ran" if table.randomized else "not_assessed",
                count=len(table.variables),
                detail="Per-variable simulation; combined test only with confirmed independence."
                if table.randomized
                else "Randomization assumption not confirmed.",
            )
    else:
        for w in works:
            collector.coverage.append(
                Coverage(
                    work_id=w.id,
                    source="D2/D3",
                    status="skipped",
                    detail="No reviewer-confirmed scale/sample-size/baseline assumptions supplied. JATS tables exported for review.",
                )
            )
    run_manifest = {
        "python": platform.python_version(),
        "image_profile": "experimental-compression" if experimental_compression else "standard",
        "packages": {
            name: version(name)
            for name in ("numpy", "opencv-python-headless", "scipy", "pillow", "pydantic")
        },
        "detector_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).parent / "detectors").glob("*.py")
        },
        "input_sha256": {a.artifact_id: a.sha256 for a in artifacts},
    }
    (output / "run-manifest.json").write_text(json.dumps(run_manifest, indent=2))
    review = {
        "plan": detector_plan,
        "model_used": False,
        "image_profile": "experimental-compression" if experimental_compression else "standard",
    }
    if llm:
        try:
            selection = provider.select(
                {
                    "findings": [f.model_dump(mode="json") for f in findings],
                    "captions": captions,
                    "available_artifact_types": review["plan"],
                }
            )
            known = {f.id for f in findings}
            review.update(
                model_used=True,
                priority=[fid for fid in selection.finding_ids if fid in known],
                rejected_ids=[fid for fid in selection.finding_ids if fid not in known],
                questions=selection.questions,
            )
        except Exception as exc:
            review["provider_error"] = type(exc).__name__
    if review.get("priority"):
        order = {fid: i for i, fid in enumerate(review["priority"])}
        findings.sort(key=lambda f: order.get(f.id, len(order)))
    # Coalesce byte-for-byte identical detector outputs only. Conflicting IDs must
    # survive to the verifier, which rejects ambiguity instead of keeping a winner.
    unique = {}
    for f in findings:
        unique.setdefault(f.model_dump_json(), f)
    findings = list(unique.values())
    (output / "findings.json").write_text(
        json.dumps([f.model_dump(mode="json") for f in findings], indent=2)
    )
    (output / "panels.json").write_text(
        json.dumps(
            [
                {
                    "id": p.id,
                    "artifact_id": p.artifact_id,
                    "work_id": p.work_id,
                    "caption": p.caption,
                    "box": p.box,
                }
                for p in panels
            ],
            indent=2,
        )
    )
    return write_report(
        output,
        author,
        works,
        artifacts,
        findings,
        collector.coverage,
        review=review,
        detector_coverage=ledger.finish(),
    )
