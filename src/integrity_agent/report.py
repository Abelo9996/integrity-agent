"""Deterministic claim verifier and escaped static HTML/JSON rendering."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .agent import REVIEW_QUESTIONS
from .assessment import AssessmentLedger, coverage_summary
from .models import FOOTER, Artifact, Author, Claim, Coverage, Finding, Work
from .report_html import render_report
from .report_snapshot import render_snapshot
from .report_summary import reading_summary
from .review_groups import review_groups


def claims_from_findings(findings: list[Finding]) -> list[Claim]:
    return [
        Claim(finding_id=f.id, artifact_ids=f.artifact_ids, text=f.statement, tier=f.tier)
        for f in findings
    ]


def verify(claims: list[Claim], findings: list[Finding], artifacts: list[Artifact]):
    """Validate unique references and exact detector text; file checks follow at rendering."""
    indexed = {f.id: f for f in findings}
    known = {a.artifact_id: a for a in artifacts}
    finding_counts = Counter(f.id for f in findings)
    artifact_counts = Counter(a.artifact_id for a in artifacts)
    claim_counts = Counter(c.finding_id for c in claims)
    accepted, rejected = [], []
    for claim in claims:
        f = indexed.get(claim.finding_id)
        reason = None
        if f is None:
            reason = "unknown finding ID"
        elif finding_counts[f.id] != 1:
            reason = "ambiguous duplicate finding ID"
        elif claim_counts[f.id] != 1:
            reason = "duplicate claims for finding ID"
        elif claim.text != f.statement or claim.tier != f.tier:
            reason = "claim differs from detector output"
        elif set(claim.artifact_ids) != set(f.artifact_ids):
            reason = "artifact references differ from detector output"
        elif any(a not in known for a in f.artifact_ids):
            reason = "unknown artifact ID"
        elif any(artifact_counts[a] != 1 for a in f.artifact_ids):
            reason = "ambiguous duplicate artifact ID"
        elif set(f.work_ids) != {known[a].work_id for a in f.artifact_ids}:
            reason = "work/artifact association mismatch"
        elif f.detector == "D1" and f.kind in ("image-reuse", "copy-move") and not f.evidence_files:
            reason = "image finding lacks evidence files"
        elif len(f.evidence_files) != len(set(f.evidence_files)):
            reason = "duplicate evidence file references"
        elif set(f.evidence_files) != set(f.evidence_sha256):
            reason = "evidence file/digest references differ"
        elif any(
            not re.fullmatch(r"[a-f0-9]{64}", digest) for digest in f.evidence_sha256.values()
        ):
            reason = "invalid evidence SHA-256"
        elif any(not safe_evidence_path(path) for path in f.evidence_files):
            reason = "unsafe evidence path"
        if reason:
            rejected.append({"finding_id": claim.finding_id, "reason": reason})
        else:
            accepted.append(claim)
    return accepted, rejected


def safe_evidence_path(value: str) -> bool:
    """Canonical relative paths whose filesystem and browser interpretation agree."""
    p = Path(value)
    return bool(
        not p.is_absolute()
        and len(p.parts) >= 2
        and p.parts[0] == "evidence"
        and ".." not in p.parts
        and p.as_posix() == value
        and not any(c in value for c in "\\%?#")
        and all(ord(c) >= 32 for c in value)
    )


def verify_files(
    root: Path, claims: list[Claim], findings: list[Finding], artifacts: list[Artifact]
):
    """Validate bytes for structurally accepted claims, failing closed on evidence gaps."""
    indexed = {f.id: f for f in findings}
    known = {a.artifact_id: a for a in artifacts}
    cache: dict[Path, str | None] = {}
    evidence_root = root.resolve() / "evidence"

    def digest(path: Path):
        if path not in cache:
            try:
                if not path.is_file():
                    cache[path] = None
                else:
                    with path.open("rb") as stream:
                        cache[path] = hashlib.file_digest(stream, "sha256").hexdigest()
            except (OSError, ValueError):
                cache[path] = None
        return cache[path]

    accepted, rejected = [], []
    for claim in claims:
        f = indexed[claim.finding_id]
        reason = None
        if any(digest(Path(known[a].path)) != known[a].sha256 for a in claim.artifact_ids):
            reason = "artifact file absent or SHA-256 mismatch"
        else:
            for name in f.evidence_files:
                try:
                    path = (root / name).resolve(strict=True)
                except (OSError, ValueError, RuntimeError):
                    reason = "evidence file absent or unreadable"
                    break
                if not path.is_relative_to(evidence_root):
                    reason = "evidence resolves outside report evidence directory"
                    break
                if digest(path) != f.evidence_sha256[name]:
                    reason = "evidence file absent or SHA-256 mismatch"
                    break
        if reason:
            rejected.append({"finding_id": claim.finding_id, "reason": reason})
        else:
            accepted.append(claim)
    return accepted, rejected


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
    detector_coverage=None,
):
    root.mkdir(parents=True, exist_ok=True)
    accepted, rejected = verify(
        claims if claims is not None else claims_from_findings(findings), findings, artifacts
    )
    accepted, file_rejections = verify_files(root, accepted, findings, artifacts)
    rejected.extend(file_rejections)
    accepted_ids = {c.finding_id for c in accepted}
    verified = [f for f in findings if f.id in accepted_ids]
    groups = review_groups(verified, artifacts)
    detector_coverage = (
        detector_coverage
        if detector_coverage is not None
        else AssessmentLedger(w.id for w in works).finish()
    )
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
        "works_analyzed": len({c.work_id for c in detector_coverage if c.status == "ran"}),
        "works_attempted": len(works),
        "raw_verified_findings": len(verified),
        "review_groups": len(groups),
        "detector_checks": coverage_summary(detector_coverage),
        "author_profile_works_count": author.works_count,
        "artifacts_collected": len(artifacts),
    }
    report = {
        "schema_version": "1.4",
        "author": author.model_dump(mode="json"),
        "summary": summary,
        "reading_summary": reading_summary(works, artifacts, verified, coverage, detector_coverage),
        "works": [w.model_dump(mode="json") for w in works],
        "artifacts": [a.model_dump(mode="json") for a in artifacts],
        "findings": [f.model_dump(mode="json") for f in verified],
        "claims": [c.model_dump(mode="json") for c in accepted],
        "coverage": [c.model_dump(mode="json") for c in coverage],
        "detector_coverage": [c.model_dump(mode="json") for c in detector_coverage],
        "review_groups": groups,
        "verification": {"accepted": len(accepted), "rejected": rejected},
        "review": review or {"questions": list(REVIEW_QUESTIONS.values())},
        "footer": FOOTER,
    }
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (root / "verifier-log.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    (root / "report.html").write_text(render_report(report), encoding="utf-8")
    (root / "summary.svg").write_text(render_snapshot(report), encoding="utf-8")
    return report
