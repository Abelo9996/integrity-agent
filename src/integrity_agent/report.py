"""Deterministic claim verifier and escaped static HTML/JSON rendering."""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from .agent import REVIEW_QUESTIONS
from .models import FOOTER, Artifact, Author, Claim, Coverage, Finding, Work


def claims_from_findings(findings: list[Finding]) -> list[Claim]:
    return [
        Claim(finding_id=f.id, artifact_ids=f.artifact_ids, text=f.statement, tier=f.tier)
        for f in findings
    ]


def verify(claims: list[Claim], findings: list[Finding], artifacts: list[Artifact]):
    indexed = {f.id: f for f in findings}
    known = {a.artifact_id: a for a in artifacts}
    accepted, rejected = [], []
    for claim in claims:
        f = indexed.get(claim.finding_id)
        reason = None
        if f is None:
            reason = "unknown finding ID"
        elif claim.text != f.statement or claim.tier != f.tier:
            reason = "claim differs from detector output"
        elif set(claim.artifact_ids) != set(f.artifact_ids):
            reason = "artifact references differ from detector output"
        elif any(a not in known for a in f.artifact_ids):
            reason = "unknown artifact ID"
        elif set(f.work_ids) != {known[a].work_id for a in f.artifact_ids}:
            reason = "work/artifact association mismatch"
        if reason:
            rejected.append({"finding_id": claim.finding_id, "reason": reason})
        else:
            accepted.append(claim)
    return accepted, rejected


def safe_source(url: str):
    return url if urlsplit(url).scheme == "https" else ""


def write_report(
    root: Path,
    author: Author,
    works: list[Work],
    artifacts: list[Artifact],
    findings: list[Finding],
    coverage: list[Coverage],
    *,
    claims=None,
    review=None,
):
    root.mkdir(parents=True, exist_ok=True)
    accepted, rejected = verify(
        claims if claims is not None else claims_from_findings(findings), findings, artifacts
    )
    invalid_files = set()
    for artifact in artifacts:
        path = Path(artifact.path)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            invalid_files.add(artifact.artifact_id)
    for claim in list(accepted):
        if invalid_files.intersection(claim.artifact_ids):
            accepted.remove(claim)
            rejected.append(
                {
                    "finding_id": claim.finding_id,
                    "reason": "artifact file absent or SHA-256 mismatch",
                }
            )
    accepted_ids = {c.finding_id for c in accepted}
    verified = [f for f in findings if f.id in accepted_ids]
    strong = {w for f in verified if f.tier == "strong" for w in f.work_ids}
    summary = {
        "papers_with_strong_findings": len(strong),
        "years": dict(Counter(str(w.year) for w in works if w.id in strong)),
        "venues": dict(Counter(w.venue for w in works if w.id in strong)),
        "papers_with_recorded_retractions": len(
            {
                wid
                for f in verified
                if f.kind == "publication-update" and f.measurements.get("type") == "retraction"
                for wid in f.work_ids
            }
        ),
        "papers_indexed": len(works),
        "artifacts_collected": len(artifacts),
    }
    report = {
        "schema_version": "1.0",
        "author": author.model_dump(mode="json"),
        "summary": summary,
        "works": [w.model_dump(mode="json") for w in works],
        "artifacts": [a.model_dump(mode="json") for a in artifacts],
        "findings": [f.model_dump(mode="json") for f in verified],
        "claims": [c.model_dump(mode="json") for c in accepted],
        "coverage": [c.model_dump(mode="json") for c in coverage],
        "verification": {"accepted": len(accepted), "rejected": rejected},
        "review": review or {"questions": list(REVIEW_QUESTIONS.values())},
        "footer": FOOTER,
    }
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (root / "verifier-log.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    esc = html.escape
    body = [
        f"<h1>Evidence review: {esc(author.name)}</h1>",
        "<p>No overall verdict is provided.</p>",
        f"<p>{summary['papers_indexed']} papers indexed; {len(artifacts)} artifacts collected; "
        f"{len(strong)} papers with strong findings.</p>",
        "<h2>Benign explanations to examine</h2><ul>"
        + "".join(f"<li>{esc(q)}</li>" for q in REVIEW_QUESTIONS.values())
        + "</ul>",
    ]
    for work in works:
        body.append(
            f"<section><h2>{esc(work.title)}</h2><p>{esc(str(work.year))} · {esc(work.venue)}</p>"
        )
        fs = [f for f in verified if work.id in f.work_ids]
        if not fs:
            body.append(
                "<p>No detector findings in the collected artifacts. This does not establish reliability or completeness.</p>"
            )
        for f in fs:
            body.append(
                f"<article><h3>{esc(f.detector)} · {esc(f.tier)}</h3><p>{esc(f.statement)}</p><code>{esc(f.id)}</code>"
            )
            body.append(
                "<details><summary>Detector measurements and assumptions</summary><pre>"
                + esc(
                    json.dumps(
                        {"parameters": f.parameters, "measurements": f.measurements}, indent=2
                    )
                )
                + "</pre></details>"
            )
            for evidence in f.evidence_files:
                p = Path(evidence)
                if p.is_absolute() or ".." in p.parts or not str(p).startswith("evidence/"):
                    continue
                body.append(
                    f'<img src="{esc(evidence, quote=True)}" alt="Detector matching evidence">'
                )
            for a in artifacts:
                if a.artifact_id in f.artifact_ids:
                    url = safe_source(a.url)
                    label = esc(a.artifact_id)
                    body.append(
                        f'<p>Source: <a href="{esc(url, quote=True)}">{label}</a> · {esc(a.license)}</p>'
                        if url
                        else f"<p>Source: {label}</p>"
                    )
            body.append(
                "<ul>"
                + "".join(f"<li>{esc(lim)}</li>" for lim in f.limitations)
                + "</ul></article>"
            )
        body.append("</section>")
    body.append(
        "<h2>Collection coverage</h2><ul>"
        + "".join(
            f"<li>{esc(c.work_id)} · {esc(c.source)} · {c.status}: {esc(c.detail)}</li>"
            for c in coverage
        )
        + "</ul>"
    )
    body.append(f"<footer>{FOOTER}</footer>")
    document = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evidence review</title><style>body{font:16px/1.55 system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#15232b;background:#fafbfc}article{border:1px solid #bac8d0;padding:20px;margin:16px 0;background:white}img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}code,a{overflow-wrap:anywhere}footer{border-top:3px solid #345;padding:20px 0;font-weight:700}h1,h2,h3{line-height:1.2}</style><body>'
        + "".join(body)
        + "</body></html>"
    )
    (root / "report.html").write_text(document, encoding="utf-8")
    return report
