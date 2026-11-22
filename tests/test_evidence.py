import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from integrity_agent.cli import app
from integrity_agent.models import Artifact, Author, Claim, Coverage, Work, finding
from integrity_agent.report import claims_from_findings, verify, write_report


def fixtures():
    a = Artifact(
        work_id="w",
        artifact_id="a",
        source="synthetic",
        url="https://example.org/a",
        linking_identifier="w",
        sha256=hashlib.sha256(b"x").hexdigest(),
        license="CC0",
        path="data/a",
    )
    f = finding("D1", "test", "review", ["w"], ["a"], "Synthetic anomaly warrants review.")
    return a, f


def test_verifier_rejects_fabrication_and_wrong_artifacts():
    a, f = fixtures()
    claims = claims_from_findings([f])
    assert len(verify(claims, [f], [a])[0]) == 1
    malicious = [
        Claim(finding_id="missing", artifact_ids=["a"], text="x", tier="review"),
        claims[0].model_copy(update={"text": "Unsupported interpretation"}),
        claims[0].model_copy(update={"tier": "strong"}),
        claims[0].model_copy(update={"artifact_ids": ["other"]}),
    ]
    accepted, rejected = verify(malicious, [f], [a])
    assert not accepted
    assert len(rejected) == 4


def test_verifier_checks_work_association():
    a, f = fixtures()
    a.work_id = "other"
    assert not verify(claims_from_findings([f]), [f], [a])[0]


def test_duplicate_finding_id_cannot_render_an_uncited_statement(tmp_path):
    a, f = fixtures()
    source = tmp_path / "source.bin"
    source.write_bytes(b"x")
    a.path = str(source)
    f.tier = "strong"
    changed = f.model_copy(update={"statement": "Second synthetic statement.", "tier": "review"})
    result = write_report(
        tmp_path,
        Author(id="synthetic", name="Synthetic"),
        [Work(id="w", title="Synthetic", author_id="synthetic")],
        [a],
        [f, changed],
        [],
        claims=claims_from_findings([changed]),
    )
    assert result["verification"]["accepted"] == 0
    assert not result["findings"]
    assert result["summary"]["papers_with_strong_findings"] == 0
    assert result["verification"]["rejected"][0]["reason"] == "ambiguous duplicate finding ID"
    html = (tmp_path / "report.html").read_text()
    assert f.statement not in html and changed.statement not in html


def test_duplicate_artifact_ids_and_claims_fail_closed():
    a, f = fixtures()
    claims = claims_from_findings([f])
    accepted, rejected = verify(claims, [f], [a, a.model_copy()])
    assert not accepted and rejected[0]["reason"] == "ambiguous duplicate artifact ID"
    accepted, rejected = verify(claims + claims, [f], [a])
    assert not accepted and len(rejected) == 2
    assert all(row["reason"] == "duplicate claims for finding ID" for row in rejected)


def image_evidence_fixture(root):
    from PIL import Image

    a, _ = fixtures()
    source = root / "source.bin"
    source.write_bytes(b"x")
    a.path = str(source)
    evidence = root / "evidence"
    evidence.mkdir()
    path = evidence / "synthetic.png"
    Image.new("RGB", (20, 20), "white").save(path)
    f = finding(
        "D1",
        "image-reuse",
        "review",
        ["w"],
        ["a"],
        "Synthetic image match warrants review.",
        evidence_files=["evidence/synthetic.png"],
        evidence_sha256={"evidence/synthetic.png": hashlib.sha256(path.read_bytes()).hexdigest()},
    )
    return a, f, path


def render_image_fixture(root, a, f):
    return write_report(
        root,
        Author(id="synthetic", name="Synthetic"),
        [Work(id="w", title="Synthetic", author_id="synthetic")],
        [a],
        [f],
        [],
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "altered",
        "missing-digest",
        "empty-evidence",
        "extra-digest",
        "bad-digest",
        "duplicate-path",
    ],
)
def test_image_claim_rejects_missing_or_altered_evidence(tmp_path, change):
    a, f, path = image_evidence_fixture(tmp_path)
    if change == "missing":
        path.unlink()
    elif change == "altered":
        path.write_bytes(b"altered synthetic bytes")
    elif change == "missing-digest":
        f.evidence_sha256 = {}
    elif change == "empty-evidence":
        f.evidence_files = []
        f.evidence_sha256 = {}
    elif change == "extra-digest":
        f.evidence_sha256["evidence/unclaimed.png"] = "0" * 64
    elif change == "bad-digest":
        f.evidence_sha256["evidence/synthetic.png"] = "not-a-digest"
    else:
        f.evidence_files.append("evidence/synthetic.png")
    result = render_image_fixture(tmp_path, a, f)
    assert result["verification"]["accepted"] == 0
    assert len(result["verification"]["rejected"]) == 1
    assert not result["findings"]
    html = (tmp_path / "report.html").read_text()
    assert f.statement not in html
    assert html.index("Verification gaps") < html.index("<section>")


@pytest.mark.parametrize(
    "name",
    [
        "../outside.png",
        "/absolute.png",
        "evidence/../outside.png",
        "evidence/%2e%2e/outside.png",
        "evidence/./synthetic.png",
        "evidence\\synthetic.png",
    ],
)
def test_image_claim_rejects_unsafe_evidence_path(tmp_path, name):
    a, f, _ = image_evidence_fixture(tmp_path)
    digest = next(iter(f.evidence_sha256.values()))
    f.evidence_files = [name]
    f.evidence_sha256 = {name: digest}
    result = render_image_fixture(tmp_path, a, f)
    assert result["verification"]["accepted"] == 0
    assert result["verification"]["rejected"][0]["reason"] == "unsafe evidence path"


@pytest.mark.parametrize("directory_link", [False, True])
def test_image_claim_rejects_symlink_escape(tmp_path, directory_link):
    a, f, path = image_evidence_fixture(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    moved = outside / "synthetic.png"
    path.rename(moved)
    if directory_link:
        path.parent.rmdir()
        path.parent.symlink_to(outside, target_is_directory=True)
    else:
        path.symlink_to(moved)
    result = render_image_fixture(tmp_path, a, f)
    assert result["verification"]["accepted"] == 0
    assert (
        result["verification"]["rejected"][0]["reason"]
        == "evidence resolves outside report evidence directory"
    )


def test_intact_evidence_passes_and_unreadable_source_rejects(tmp_path, monkeypatch):
    a, f, _ = image_evidence_fixture(tmp_path)
    assert render_image_fixture(tmp_path, a, f)["verification"]["accepted"] == 1
    original = Path.open

    def fail_source(path, *args, **kwargs):
        if path == Path(a.path):
            raise PermissionError("synthetic read denial")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_source)
    result = render_image_fixture(tmp_path, a, f)
    assert result["verification"]["accepted"] == 0
    assert (
        result["verification"]["rejected"][0]["reason"]
        == "artifact file absent or SHA-256 mismatch"
    )


def test_html_escapes_source_text(tmp_path):
    a, f = fixtures()
    source = tmp_path / "synthetic-source.bin"
    source.write_bytes(b"x")
    a.path = str(source)
    f.statement = "<script>alert(1)</script>"
    author = Author(id="synthetic", name="<b>Synthetic</b>")
    work = Work(id="w", title="<img onerror=x>", author_id=author.id)
    report = write_report(tmp_path, author, [work], [a], [f], [])
    html = (tmp_path / "report.html").read_text()
    from lxml.html import fromstring

    from integrity_agent.report_html import SCRIPT

    # Only the fixed disclosure helper is executable; source text stays escaped.
    page = fromstring(html)
    assert page.xpath("//script/text()") == [SCRIPT]
    assert not page.xpath("//*[@onerror]")
    assert "&lt;script&gt;" in html
    assert report["verification"]["accepted"] == 1


def test_demo_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["demo"])
    assert result.exit_code == 0, result.output
    report = json.loads(Path("outputs/demo/report.json").read_text())
    assert report["findings"]
    assert not report["verification"]["rejected"]
    assert Path("outputs/demo/report.html").exists()
    for f in report["findings"]:
        for path in f["evidence_files"]:
            assert (Path("outputs/demo") / path).exists()
            assert (
                hashlib.sha256((Path("outputs/demo") / path).read_bytes()).hexdigest()
                == f["evidence_sha256"][path]
            )


def test_small_region_evidence_survives_pipeline_and_verifier(tmp_path):
    import io
    from unittest.mock import Mock

    from PIL import Image

    from integrity_agent.acquisition import Collector
    from integrity_agent.evaluation_regions import region_cases
    from integrity_agent.pipeline import analyze

    case = region_cases(20)[-1]
    author = Author(id="synthetic", name="Synthetic")
    works = [Work(id=f"w{i}", title=f"Synthetic bands {i}", author_id=author.id) for i in (0, 1)]
    collector = Collector(Mock(), tmp_path / "data")
    for work, pixels in zip(works, (case.source, case.target), strict=True):
        stream = io.BytesIO()
        Image.fromarray(pixels).save(stream, format="PNG")
        collector.save(
            work,
            stream.getvalue(),
            "synthetic",
            f"https://example.org/{work.id}.png",
            work.id,
            "CC0",
            ".png",
        )
    output = tmp_path / "report"
    result = analyze(collector, author, works, output, network=False, experimental_compression=True)
    findings = [
        f
        for f in result["findings"]
        if f["parameters"].get("method") == "component-pixel-corroboration-v2"
    ]
    assert findings
    assert not result["verification"]["rejected"]
    for f in findings:
        assert f["measurements"]["source_figure_points"]
        assert f["measurements"]["target_figure_points"]
        assert all((output / name).is_file() for name in f["evidence_files"])
    assert (output / "report.html").is_file()


def test_limited_run_displays_scope_before_paper_results(tmp_path):
    author = Author(id="synthetic", name="Synthetic", works_count=100)
    note = "Explicit limit: analyzed 1 of 100 indexed works"
    report = write_report(
        tmp_path,
        author,
        [Work(id="w", title="Synthetic paper", author_id=author.id)],
        [],
        [],
        [Coverage(work_id=author.id, source="work limit", status="skipped", detail=note)],
    )
    rendered = (tmp_path / "report.html").read_text()
    assert rendered.index(note) < rendered.index("<section>")
    assert "1 works attempted" in rendered
    assert report["summary"]["works_analyzed"] == 0
    assert report["summary"]["works_attempted"] == 1
    assert report["summary"]["author_profile_works_count"] == 100


def test_run_requires_contact_email(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INTEGRITY_CONTACT_EMAIL", raising=False)
    result = CliRunner().invoke(app, ["run", "--name", "Synthetic Person"])
    assert result.exit_code == 1
    assert "contact email" in result.output


def test_orcid_run_end_to_end_with_offline_api_contract(tmp_path, monkeypatch):
    from unittest.mock import Mock

    import integrity_agent.cli as cli
    from integrity_agent.evaluation import save_demo_images

    monkeypatch.chdir(tmp_path)
    author = Author(
        id="https://openalex.org/A999999999",
        name="Synthetic Researcher",
        orcid="https://orcid.org/0000-0000-0000-0000",
    )
    work_list = [Work(id=f"W{i}", title=f"Synthetic {i}", author_id=author.id) for i in (1, 2)]
    paths = save_demo_images(tmp_path / "data/synthetic")
    monkeypatch.setattr(cli, "Transport", Mock(return_value=Mock()))
    monkeypatch.setattr(cli, "resolve", lambda *a, **k: [author])
    monkeypatch.setattr(
        cli,
        "orcid_record",
        lambda *a: {"person": {"name": {"given-names": {"value": "Synthetic"}}}},
    )
    monkeypatch.setattr(cli, "works", lambda *a: work_list)

    def collect(self, work):
        p = paths[int(work.id[-1]) - 1]
        self.save(work, p.read_bytes(), "synthetic", "synthetic:" + p.name, work.id, "CC0", ".png")

    monkeypatch.setattr(cli.Collector, "collect", collect)
    monkeypatch.setattr(cli, "retraction_watch", lambda *a: None)
    monkeypatch.setattr(cli, "field_baselines", lambda *a: None)
    result = CliRunner().invoke(
        app, ["run", "--orcid", "0000-0000-0000-0000"], input="A999999999\n"
    )
    assert result.exit_code == 0, result.output
    report = json.loads(next(Path("outputs").glob("run-*/report.json")).read_text())
    assert report["findings"] and not report["verification"]["rejected"]


def test_file_tampering_rejects_report_claim(tmp_path):
    a, f = fixtures()
    p = tmp_path / "source.bin"
    p.write_bytes(b"tampered")
    a.path = str(p)
    report = write_report(
        tmp_path,
        Author(id="synthetic", name="Synthetic"),
        [Work(id="w", title="Synthetic", author_id="synthetic")],
        [a],
        [f],
        [],
    )
    assert report["verification"]["accepted"] == 0
    assert report["verification"]["rejected"][0]["reason"].endswith("SHA-256 mismatch")


def test_pdf_provider_failure_preserves_native_image_evidence(tmp_path):
    import io
    from unittest.mock import Mock

    import numpy as np
    import pymupdf
    from PIL import Image

    from integrity_agent.acquisition import Collector
    from integrity_agent.agent import ReviewSelection
    from integrity_agent.evaluation import synthetic_image
    from integrity_agent.pipeline import analyze

    collector = Collector(Mock(), tmp_path / "data")
    author = Author(id="synthetic", name="Synthetic")
    works = []
    base = synthetic_image(71)
    for i, array in enumerate((base, np.fliplr(base).copy())):
        work = Work(id=f"w{i}", title=f"Synthetic PDF {i}", author_id="synthetic")
        works.append(work)
        img = io.BytesIO()
        Image.fromarray(array).save(img, format="PNG")
        document = pymupdf.open()
        page = document.new_page()
        page.insert_image(pymupdf.Rect(0, 0, 320, 320), stream=img.getvalue())
        content = document.tobytes()
        document.close()
        collector.save(work, content, "synthetic", f"synthetic:pdf{i}", work.id, "CC0", ".pdf")
    provider = Mock()
    provider.extract_pdf.side_effect = ValueError("Synthetic provider failure")
    provider.select.return_value = ReviewSelection()
    report = analyze(
        collector, author, works, tmp_path / "outputs", llm=True, provider=provider, network=False
    )
    assert any(f["detector"] == "D1" for f in report["findings"])
    assert not report["verification"]["rejected"]
    assert any(
        c["source"] == "PDF structured extraction" and c["status"] == "failed"
        for c in report["coverage"]
    )
