"""Summary semantics must preserve evidence and distinguish unknown from negative."""

import hashlib
import json

from lxml import etree, html

from integrity_agent.models import Artifact, Author, Coverage, DetectorCoverage, Work, finding
from integrity_agent.report import write_report
from integrity_agent.work_types import notice_title


def source(root, wid, aid):
    path = root / f"{aid}.txt"
    path.write_bytes(b"synthetic source")
    return Artifact(
        work_id=wid,
        artifact_id=aid,
        source="synthetic",
        url="https://example.org/source",
        linking_identifier=wid,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        license="CC0",
        path=str(path),
        media_type="text/plain",
    )


def test_summary_counts_results_not_unique_notices_or_confirmed_issues(tmp_path):
    author = Author(id="author", name="Synthetic researcher")
    works = [Work(id="w", title="Synthetic paper", author_id=author.id)]
    artifacts = [source(tmp_path, "w", aid) for aid in ("a", "b")]
    findings = [
        finding(
            "D5",
            "publication-update",
            "info",
            ["w"],
            [a.artifact_id],
            "An identifier-linked retraction notice is recorded for this paper.",
            measurements={"type": "retraction", "notice_doi": "synthetic-notice"},
        )
        for a in artifacts
    ]
    report = write_report(tmp_path, author, works, artifacts, findings, [])
    brief = report["reading_summary"]
    row = brief["categories"][0]
    assert row["result_count"] == 2
    assert row["work_ids"] == ["w"]
    assert set(row["finding_ids"]) == {f.id for f in findings}
    assert row["artifact_ids"] == ["a", "b"]
    assert row["status_work_ids"] == {"retraction": ["w"]}
    assert brief["counts_by_tier"] == {"strong": 0, "review": 0, "info": 2}
    assert not brief["priority_finding_ids"]
    assert brief["outcome"]["state"] == "not_assessed"
    assert brief["cards"][0]["metric"] == "1"
    assert brief["cards"][0]["finding_ids"] == row["finding_ids"]
    review = report["paper_review"]
    assert review["publication_action_work_ids"] == ["w"]
    assert review["retraction_work_ids"] == ["w"]
    assert review["retraction_work_ids_with_core_checks"] == []
    assert review["queues"]["notices"][0]["notice_ids"] == [f.id for f in findings]
    assert "not independent issues" in row["explanation"]
    assert len(report["findings"]) == len(report["claims"]) == 2


def test_failed_verification_never_enters_summary_or_priority(tmp_path):
    author = Author(id="author", name="Synthetic")
    work = Work(id="w", title="Synthetic", author_id=author.id)
    a = source(tmp_path, work.id, "a")
    f = finding("D2", "test", "strong", [work.id], [a.artifact_id], "Synthetic inconsistency.")
    (tmp_path / "a.txt").write_text("changed")
    report = write_report(tmp_path, author, [work], [a], [f], [])
    assert not report["reading_summary"]["categories"]
    assert not report["reading_summary"]["priority_finding_ids"]
    assert not report["reading_summary"]["outcome"]["finding_ids"]
    assert report["reading_summary"]["outcome"]["state"] != "review_required"
    assert not any(report["reading_summary"]["counts_by_tier"].values())
    rendered = (tmp_path / "report.html").read_text()
    assert f.statement not in rendered
    assert "Verification gaps" in rendered


def test_coverage_uses_distinct_work_records_and_does_not_hide_failures(tmp_path):
    author = Author(id="author", name="Synthetic")
    works = [Work(id=f"w{i}", title=f"Synthetic {i}", author_id=author.id) for i in (1, 2)]
    events = [
        DetectorCoverage(
            work_id="w1",
            detector="D1",
            check=check,
            status=status,
            input_count=3,
            detail="Synthetic check",
        )
        for check, status in (("copy-move", "ran"), ("copy-move", "ran"), ("image-reuse", "failed"))
    ]
    events.append(
        DetectorCoverage(
            work_id="unknown",
            detector="D1",
            check="copy-move",
            status="ran",
            input_count=1,
            detail="Out of scope",
        )
    )
    report = write_report(tmp_path, author, works, [], [], [], detector_coverage=events)
    brief = report["reading_summary"]
    d1, d2 = brief["detector_coverage"][:2]
    assert d1["works_with_completed_check"] == 1
    assert d1["works_without_completed_check"] == 1
    assert d1["work_ids_with_failed_check"] == ["w1"]
    assert d1["status"] == "some_checks_ran"
    assert d2["status"] == "not_assessed"
    assert "Summary statistics" in brief["missing_core_checks"]
    assert "Images" not in brief["missing_core_checks"]
    rendered = (tmp_path / "report.html").read_text()
    assert report["paper_review"]["queues"]["checked"][0]["cells"]["D1"] == "partial"
    assert "at least one completed check" in rendered


def test_notice_context_is_labeled_as_title_cue_and_keeps_matching_ids(tmp_path):
    author = Author(id="author", name="Synthetic")
    works = [
        Work(id=f"w{i}", title=title, author_id=author.id)
        for i, title in enumerate(
            [
                "Retraction Note to: Synthetic A",
                "Correction: Synthetic B",
                "Retraction mechanisms in synthetic fibers",
            ]
        )
    ]
    artifacts = [source(tmp_path, w.id, f"a{i}") for i, w in enumerate(works)]
    findings = [
        finding(
            "D6",
            "text-reuse",
            "info",
            ["w0", f"w{i}"],
            ["a0", f"a{i}"],
            "Long exact token sequences recur across sections of these papers.",
        )
        for i in (1, 2)
    ]
    report = write_report(tmp_path, author, works, artifacts, findings, [])
    row = report["reading_summary"]["categories"][0]
    assert row["notice_title_finding_ids"] == [findings[0].id]
    assert row["result_count"] == 2
    rendered = (tmp_path / "report.html").read_text()
    assert "1 of 2 text matches" in rendered
    assert "notice-style titles" in rendered
    assert "may explain" in rendered
    assert not notice_title(works[2].title)
    assert not notice_title("A study of correction methods")
    assert notice_title("ERRATUM TO: synthetic")


def test_priority_order_collapsed_evidence_and_every_internal_link_resolves(tmp_path):
    author = Author(id="author", name="Synthetic <researcher>")
    work = Work(id="w", title="Synthetic work", author_id=author.id)
    a = source(tmp_path, work.id, "a")
    findings = [
        finding("D2", "synthetic-test", tier, ["w"], ["a"], f"Synthetic {tier} result.")
        for tier in ("info", "strong", "review")
    ]
    report = write_report(tmp_path, author, [work], [a], findings, [])
    brief = report["reading_summary"]
    assert [c["tier"] for c in brief["categories"]] == ["strong", "review", "info"]
    assert brief["priority_work_ids"] == ["w"]
    assert len(brief["priority_finding_ids"]) == 2
    assert brief["outcome"]["state"] == "review_required"
    assert brief["outcome"]["finding_ids"] == brief["priority_finding_ids"]
    assert brief["outcome"]["artifact_ids"] == ["a"]
    page = html.fromstring((tmp_path / "report.html").read_text())
    ids = page.xpath("//*[@id]/@id")
    assert len(ids) == len(set(ids))
    for href in page.xpath('//a[starts-with(@href,"#")]/@href'):
        assert href[1:] in ids
    assert not page.xpath("//details[@open]")
    assert page.xpath('//details[@class="result"]')
    assert len(page.xpath('//details[@class="result"]')) == 3
    assert page.xpath("//h1/text()") == [author.name]
    for f in findings:
        assert f.id in page.text_content()
    assert report["verification"] == {"accepted": 3, "rejected": []}


def test_empty_run_and_scope_limit_are_not_presented_as_success(tmp_path):
    author = Author(id="author", name="Synthetic", works_count=20)
    report = write_report(
        tmp_path,
        author,
        [],
        [],
        [],
        [
            Coverage(
                work_id=author.id, source="work limit", status="skipped", detail="Explicit limit"
            )
        ],
    )
    brief = report["reading_summary"]
    assert len(brief["missing_core_checks"]) == 4
    assert not brief["collection_attempts"]
    assert all(c["status"] == "not_assessed" for c in brief["detector_coverage"])
    assert brief["outcome"]["state"] == "no_records"
    rendered = (tmp_path / "report.html").read_text()
    assert rendered.index("Explicit limit") < rendered.index('id="summary"')
    assert "No research files had a completed check" in rendered
    assert not any(report["paper_review"]["queues"].values())


def test_documents_keep_metadata_parent_links_and_notice_cue(tmp_path):
    author = Author(id="author", name="Synthetic")
    work = Work(id="w", title="Correction: Synthetic study", author_id=author.id)
    metadata = source(tmp_path, "w", "metadata")
    metadata.path = str(tmp_path / "metadata.json")
    (tmp_path / "metadata.json").write_bytes(b"synthetic source")
    document = source(tmp_path, "w", "document")
    document.path = str(tmp_path / "notice.pdf")
    (tmp_path / "notice.pdf").write_bytes(b"synthetic source")
    document.parent_artifact_id = metadata.artifact_id
    report = write_report(tmp_path, author, [work], [metadata, document], [], [])
    collection = report["reading_summary"]["collection"]
    assert collection["document_artifact_ids"] == [document.artifact_id]
    assert collection["notice_title_document_ids"] == [document.artifact_id]
    assert collection["publication_record_count"] == 1
    assert not collection["core_checked_work_ids"]
    page = html.fromstring((tmp_path / "report.html").read_text())
    assert len(page.xpath('//*[@id="queue-notice_documents"]//details[@class="paper-row"]')) == 1
    assert report["paper_review"]["queues"]["notice_documents"][0]["artifact_ids"] == [
        "metadata",
        "document",
    ]


def test_completed_checks_without_results_are_not_declared_clean(tmp_path):
    author = Author(id="author", name="Synthetic")
    work = Work(id="w", title="Synthetic work", author_id=author.id)
    checks = [
        DetectorCoverage(
            work_id=work.id,
            detector="D1",
            check="copy-move",
            status="ran",
            input_count=1,
            detail="Synthetic completed check",
        )
    ]
    report = write_report(tmp_path, author, [work], [], [], [], detector_coverage=checks)
    brief = report["reading_summary"]
    assert brief["outcome"]["state"] == "no_priority_signals"
    assert brief["collection"]["core_checked_work_ids"] == [work.id]
    assert "Missing inputs" in brief["outcome"]["explanation"]
    assert "clean" not in brief["outcome"]["title"].lower()


def test_overview_prioritizes_unique_papers_and_links_to_evidence(tmp_path):
    author = Author(id="author", name="Synthetic")
    work = Work(id="w", title="Synthetic work", author_id=author.id)
    a = source(tmp_path, work.id, "a")
    findings = [
        finding("D2", kind, "review", [work.id], [a.artifact_id], f"Synthetic {kind}.")
        for kind in ("first", "second", "third", "fourth")
    ]
    report = write_report(tmp_path, author, [work], [a], findings, [])
    page = html.fromstring((tmp_path / "report.html").read_text())
    overview = page.get_element_by_id("summary")
    assert len(overview.xpath('.//details[@class="paper-row"]')) == 1
    assert overview.xpath('.//b[@aria-label="Review signal"]')
    assert report["paper_review"]["queues"]["signals"][0]["signal_ids"] == [f.id for f in findings]
    assert len(page.get_element_by_id("results").xpath('.//details[@class="category"]')) == 4
    assert len(overview.text_content().split()) < 350
    assert not overview.xpath(".//pre | .//table")
    assert all(f.id not in overview.text_content() for f in findings)
    assert len(report["reading_summary"]["cards"]) == 4
    assert page.xpath("//a[@data-view]/@data-view") == ["summary", "results", "audit"]


def test_vector_summary_preserves_verified_data_links_and_visible_cards(tmp_path):
    import pymupdf

    author = Author(id="author", name="Synthetic <script>alert(1)</script>")
    work = Work(id="w", title="Synthetic work", author_id=author.id)
    a = source(tmp_path, work.id, "a")
    good = finding(
        "D5",
        "publication-update",
        "info",
        ["w"],
        ["a"],
        "Synthetic correction recorded.",
        measurements={"type": "correction"},
    )
    bad = finding("D2", "synthetic", "strong", ["w"], ["absent"], "Unsupported statement.")
    report = write_report(tmp_path, author, [work], [a], [good, bad], [])
    svg_bytes = (tmp_path / "summary.svg").read_bytes()
    svg = etree.fromstring(svg_bytes)
    ns = {"s": "http://www.w3.org/2000/svg"}
    metadata = json.loads(svg.xpath("string(s:metadata)", namespaces=ns))
    assert metadata == report["reading_summary"]
    assert metadata["cards"][0]["finding_ids"] == [good.id]
    assert bad.id not in svg_bytes.decode()
    assert not svg.xpath("//s:script", namespaces=ns)
    page = html.fromstring((tmp_path / "report.html").read_text())
    for link in svg.xpath("//s:a/@href", namespaces=ns):
        assert link.startswith("report.html#")
        assert page.get_element_by_id(link.split("#")[1]) is not None
    # Catch unsupported vector constructs that could make card text disappear in export.
    with pymupdf.open(stream=svg_bytes, filetype="svg") as source_svg:
        pdf_bytes = source_svg.convert_to_pdf()
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        text = doc[0].get_text()
        assert "Records with publication actions" in text
        assert "Verification gaps: 1 claims excluded" in text
        assert "Unsupported statement" not in text
        assert len(doc) == 1


def test_file_view_links_exact_inputs_and_notice_without_flagging_parent(tmp_path):
    from urllib.parse import unquote

    author = Author(id="author", name="Synthetic")
    paper = Work(id="w", title="Synthetic paper", author_id=author.id, doi="10.0000/paper")
    notice = Work(
        id="n", title="Retraction: Synthetic paper", author_id=author.id, doi="10.0000/notice"
    )
    data = tmp_path / "data"
    data.mkdir()
    output = tmp_path / "outputs"
    pdf = source(data, "w", "paper")
    image = source(data, "w", "figure")
    notice_pdf = source(data, "n", "notice")
    for artifact, name in [
        (pdf, "original #1.pdf"),
        (image, "figure.png"),
        (notice_pdf, "publisher-notice.pdf"),
    ]:
        path = data / name
        path.write_bytes(b"synthetic source")
        artifact.path = str(path)
    image.parent_artifact_id = pdf.artifact_id
    image.relation = "native PDF embedded image embedded-4.png"
    metadata = source(data, "w", "metadata")
    unexamined = source(data, "w", "unexamined")
    checked = DetectorCoverage(
        work_id="w",
        detector="D1",
        check="copy-move",
        status="ran",
        input_count=1,
        artifact_ids=[image.artifact_id],
        detail="Synthetic image check",
    )
    invalid_event = checked.model_copy(
        update={"work_id": "n", "artifact_ids": [unexamined.artifact_id]}
    )
    process = finding(
        "D5",
        "publication-update",
        "info",
        ["w"],
        ["metadata"],
        "Synthetic retraction recorded.",
        measurements={"type": "retraction", "notice_doi": notice.doi},
    )
    image_signal = finding(
        "D1",
        "copy-move",
        "review",
        ["w"],
        ["figure"],
        "Synthetic figure warrants review.",
        evidence_files=["evidence/synthetic.png"],
        evidence_sha256={
            "evidence/synthetic.png": hashlib.sha256(b"synthetic overlay").hexdigest()
        },
    )
    evidence = output / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "synthetic.png").write_bytes(b"synthetic overlay")
    report = write_report(
        output,
        author,
        [paper, notice],
        [pdf, image, notice_pdf, metadata, unexamined],
        [process, image_signal],
        [],
        detector_coverage=[checked, invalid_event],
    )
    assert report["file_review"]["flagged_files"] == [
        {"artifact_id": "figure", "finding_ids": [image_signal.id]},
    ]
    assert report["file_review"]["checked_files"] == [
        {
            "file_id": "paper",
            "input_ids": ["figure"],
            "detectors": ["D1"],
            "flagged_input_ids": ["figure"],
        },
    ]
    page = html.fromstring((output / "report.html").read_bytes())
    flagged = page.get_element_by_id("files-flagged")
    assert flagged.xpath(".//img/@src") == ["evidence/synthetic.png"]
    assert "../data/figure.png" in flagged.xpath(".//a/@href")
    assert "original #1.pdf" not in flagged.text_content()
    checked_section = page.get_element_by_id("files-checked")
    file_link = checked_section.xpath(".//a/@href")[0]
    assert (output / unquote(file_link)).resolve() == data / "original #1.pdf"
    assert "1 embedded image checked" in checked_section.text_content()
    assert "unexamined" not in checked_section.text_content()
    notice_links = page.get_element_by_id("files-notices").xpath(".//a/@href")
    assert {
        "https://doi.org/10.0000/paper",
        "https://doi.org/10.0000/notice",
        "../data/publisher-notice.pdf",
    } <= set(notice_links)
