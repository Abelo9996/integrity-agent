import hashlib
import json
from unittest.mock import Mock

from integrity_agent.acquisition import Collector
from integrity_agent.models import Artifact, Author, Work, finding
from integrity_agent.pipeline import analyze
from integrity_agent.report import write_report


def test_runtime_coverage_distinguishes_failed_missing_and_no_findings(tmp_path):
    author = Author(id="synthetic", name="Synthetic")
    work = Work(id="w", title="Synthetic", author_id=author.id)
    collector = Collector(Mock(), tmp_path / "data")
    collector.save(
        work, b"x,y\n1,2\n3,4\n5,6\n7,8\n", "synthetic", "synthetic:table", "w", "CC0", ".csv"
    )
    collector.save(work, b"broken image", "synthetic", "synthetic:image", "w", "CC0", ".png")
    report = analyze(collector, author, [work], tmp_path / "outputs", network=False)
    checks = report["detector_coverage"]
    assert any(c["detector"] == "D1" and c["status"] == "failed" for c in checks)
    assert any(
        c["check"] == "repeated-rows" and c["status"] == "ran" and c["input_count"] == 4
        for c in checks
    )
    assert any(c["detector"] == "D3" and c["status"] == "not_assessed" for c in checks)
    assert not report["findings"]
    assert {c["detector"] for c in checks} == {f"D{i}" for i in range(1, 7)}


def test_grouping_preserves_claims_and_rejects_ambiguous_ids(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"synthetic source")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "same.png").write_bytes(b"synthetic overlay")
    artifacts = [
        Artifact(
            work_id="w",
            artifact_id=f"a{i}",
            source="synthetic",
            url=f"https://example.org/{i}",
            linking_identifier="w",
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            license="CC0",
            path=str(source),
        )
        for i in range(3)
    ]
    findings = [
        finding(
            "D1",
            "copy-move",
            "review",
            ["w"],
            [a.artifact_id],
            f"Panel {a.artifact_id} has repeated pixels.",
            parameters={"method": "synthetic"},
            measurements={"panel_id": a.artifact_id, "source_points": [[1, 2]]},
            evidence_files=["evidence/same.png"],
            evidence_sha256={"evidence/same.png": hashlib.sha256(b"synthetic overlay").hexdigest()},
        )
        for a in artifacts
    ]
    # A different region is a different review group, despite identical source bytes.
    findings[2].measurements["source_points"] = [[3, 4]]
    author = Author(id="synthetic", name="Synthetic")
    works = [Work(id="w", title="Synthetic", author_id=author.id)]
    report = write_report(tmp_path, author, works, artifacts, findings, [])
    assert len(report["claims"]) == 3
    assert sorted(len(g["finding_ids"]) for g in report["review_groups"]) == [1, 2]
    conflicting = findings[0].model_copy(update={"statement": "Conflicting statement"})
    report = write_report(tmp_path, author, works, artifacts, findings + [conflicting], [])
    assert all(findings[0].id not in g["finding_ids"] for g in report["review_groups"])
    assert len(report["verification"]["rejected"]) == 2
    assert json.loads((tmp_path / "report.json").read_text())["schema_version"] == "1.6"


def test_notice_text_is_excluded_and_research_overlap_retains_ids(tmp_path):
    collector = Collector(Mock(), tmp_path / "data")
    author = Author(id="author", name="Synthetic")
    works = [
        Work(id=f"w{i}", title=title, author_id=author.id)
        for i, title in enumerate(
            ["Synthetic research A", "Synthetic research B", "Retraction: Synthetic C"]
        )
    ]
    body = " ".join(f"word{i}" for i in range(80))
    document = f"<article><body><sec><title>Results</title><p>{body}</p></sec></body></article>"
    for work in works:
        collector.save(
            work,
            document.encode(),
            "synthetic",
            f"https://example.org/{work.id}",
            work.id,
            "CC0",
            ".xml",
        )
    report = analyze(collector, author, works, tmp_path / "outputs", network=False)
    overlaps = [f for f in report["findings"] if f["kind"] == "text-reuse"]
    assert len(overlaps) == 1
    assert overlaps[0]["work_ids"] == ["w0", "w1"]
    assert overlaps[0]["tier"] == "info"
    coverage = {e["work_id"]: e for e in report["detector_coverage"] if e["check"] == "text-reuse"}
    assert {wid for wid, e in coverage.items() if e["status"] == "ran"} == {"w0", "w1"}
    assert coverage["w0"]["input_count"] == 1
    assert coverage["w2"]["status"] == "not_assessed"
    assert "Notice-style" in coverage["w2"]["detail"]
