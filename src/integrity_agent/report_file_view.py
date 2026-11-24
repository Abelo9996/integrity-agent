"""First-screen report for detector evidence, checked files and publisher notices."""

from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from .models import stable_id
from .paper_review import CHECK_LABELS

# These links point to original local inputs. Never make a downloaded HTML or SVG executable.
LOCAL_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".csv",
    ".tsv",
    ".xlsx",
    ".json",
    ".xml",
    ".txt",
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def finding_anchor(fid: str) -> str:
    return stable_id("result", fid)


def _local_file(artifact, root, label=None):
    path = Path(artifact["path"])
    name = label or path.name
    if path.suffix.lower() in LOCAL_SUFFIXES and path.is_file() and not path.is_symlink():
        href = quote(os.path.relpath(path.resolve(), root.resolve()), safe="/")
        return f'<a href="{esc(href)}">{esc(name)}</a>'
    return esc(name)


def _doi_link(doi, label):
    if isinstance(doi, str) and doi.lower().startswith("10."):
        return f'<a href="https://doi.org/{quote(doi, safe="/")}">{esc(label)}</a>'
    return ""


def render_file_review(report: dict, root: Path) -> str:
    file_review = report["file_review"]
    work_review = report["paper_review"]
    works = {w["id"]: w for w in report["works"]}
    files = {a["artifact_id"]: a for a in report["artifacts"]}
    findings = {f["id"]: f for f in report["findings"]}
    flags = file_review["flagged_files"]
    checked = file_review["checked_files"]
    sources_by_doi = defaultdict(list)
    for a in files.values():
        work = works.get(a["work_id"])
        if work and work["doi"] and Path(a["path"]).suffix.lower() == ".pdf":
            sources_by_doi[work["doi"].lower()].append(a)
    count = len(flags)
    headline = f"{count} detector input {'file' if count == 1 else 'files'} flagged"
    parts = [f'<div class="file-outcome"><h2>{headline}</h2>']
    retractions = len(work_review["retraction_work_ids"])
    if retractions:
        tested = len(work_review["retraction_work_ids_with_core_checks"])
        parts.append(
            f"<p><strong>{tested} of {retractions} retraction-linked records</strong> received image or data checks.</p>"
        )
    elif not checked:
        parts.append(
            "<p>No research files had a completed check with a recorded file reference.</p>"
        )
    parts.append('</div><div class="file-shortcuts">')
    parts.append(f'<a href="#files-flagged"><strong>{count}</strong> Flagged files</a>')
    parts.append(
        f'<a href="#files-notices"><strong>{len(work_review["publication_action_work_ids"])}</strong> Papers with notice records</a>'
    )
    parts.append(
        f'<a href="#files-checked"><strong>{len(checked)}</strong> Sources used for checks</a></div>'
    )
    parts.append(
        '<section class="file-section" id="files-flagged"><h2>Files that warrant review</h2>'
    )
    if not flags:
        parts.append("<p>No detector output reached review or strong tier.</p>")
    groups = {g["representative_id"]: g for g in report["review_groups"]}
    for fid in file_review["signal_group_ids"]:
        finding = findings[fid]
        group = groups[fid]
        parts.append(
            f'<article class="flag-card"><p><strong>{esc(finding["tier"].capitalize())} signal</strong></p>'
            f"<h3>{esc(finding['statement'])}</h3><ul>"
        )
        for aid in group["artifact_ids"]:
            a = files[aid]
            title = works.get(a["work_id"], {}).get("title", a["work_id"])
            parts.append(
                f"<li>{_local_file(a, root)}<small> · {esc(title)}"
                f" · {esc(a['relation'])}</small></li>"
            )
        parts.append("</ul>")
        for path in finding["evidence_files"]:
            url = esc(quote(path, safe="/"))
            parts.append(
                f'<a class="evidence-preview" href="{url}"><img loading="lazy" src="{url}" alt="Detector overlay showing the regions to review"></a>'
            )
        parts.append(
            f'<a href="#{finding_anchor(fid)}">See detector evidence and finding IDs</a></article>'
        )
    parts.append('</section><section class="file-section" id="files-notices">')
    parts.append(
        f'<h2>Publisher notices <span class="section-count">{len(work_review["publication_action_work_ids"])}</span></h2>'
    )
    parts.append(
        "<p>Existing publication actions and whether this run checked the underlying file.</p>"
    )
    action_rows = [
        row for queue in work_review["queues"].values() for row in queue if row["notice_ids"]
    ]
    action_rows.sort(
        key=lambda row: (
            row["work_id"] not in work_review["retraction_work_ids"],
            works[row["work_id"]]["title"].casefold(),
        )
    )
    for index, row in enumerate(action_rows):
        if index == 3:
            parts.append(
                f"<details><summary>Show {len(action_rows) - 3} more papers with notices</summary>"
            )
        work = works[row["work_id"]]
        anchor = stable_id("notice", work["id"])
        parts.append(f'<article class="file-row" id="{anchor}"><div><h3>{esc(work["title"])}</h3>')
        parts.append("<p>" + _doi_link(work["doi"], "Original paper") + "</p></div><div>")
        seen = set()
        for fid in row["notice_ids"]:
            f = findings[fid]
            status = (
                str(f["measurements"].get("type") or "Publication update")
                .replace("-", " ")
                .capitalize()
            )
            doi = f["measurements"].get("notice_doi")
            key = (status, doi.lower() if isinstance(doi, str) else None)
            if key in seen:
                continue
            seen.add(key)
            publisher = _doi_link(doi, f"Open {status.lower()} notice")
            parts.append(
                f'<p>{publisher or esc(status)} · <a href="#{finding_anchor(fid)}">Source record</a></p>'
            )
            if isinstance(doi, str) and sources_by_doi[doi.lower()]:
                parts.append(
                    "<p>"
                    + _local_file(sources_by_doi[doi.lower()][0], root, "Open saved notice PDF")
                    + "</p>"
                )
        label = (
            "Some image or data checks ran" if row["core_checked"] else "Images and data untested"
        )
        parts.append(f'<span class="file-status">{label}</span></div></article>')
    if len(action_rows) > 3:
        parts.append("</details>")
    if not action_rows:
        parts.append("<p>No identifier-linked publication actions recorded.</p>")
    parts.append('</section><section class="file-section" id="files-checked">')
    parts.append(
        f'<h2>Files used for checks <span class="section-count">{len(checked)}</span></h2>'
    )
    embedded = sum(aid != row["file_id"] for row in checked for aid in row["input_ids"])
    if embedded:
        parts.append(
            f"<p>Checks covered {embedded} embedded {'image' if embedded == 1 else 'images'} from the PDFs listed here. Vector plots and raw data require separate checks.</p>"
        )
    if not checked:
        parts.append("<p>No completed checks named source files.</p>")
    for index, row in enumerate(
        sorted(
            checked,
            key=lambda row: (
                works.get(files[row["file_id"]]["work_id"], {}).get("title", "").casefold(),
                row["file_id"],
            ),
        )
    ):
        if index == 6:
            parts.append(f"<details><summary>Show {len(checked) - 6} more sources</summary>")
        file = files[row["file_id"]]
        work = works.get(file["work_id"], {})
        labels = ", ".join(CHECK_LABELS[d] for d in row["detectors"])
        image_count = sum(aid != row["file_id"] for aid in row["input_ids"])
        note = (
            f" · {image_count} embedded {'image' if image_count == 1 else 'images'} checked"
            if image_count
            else ""
        )
        result = (
            f"{len(row['flagged_input_ids'])} flagged inputs"
            if row["flagged_input_ids"]
            else "No review signal"
        )
        parts.append(
            f'<article class="file-row"><div><h3>{esc(work.get("title", file["work_id"]))}</h3>'
            f'<p>{_local_file(file, root)} · {esc(labels + note)}</p></div><span class="file-status">{result}</span></article>'
        )
    if len(checked) > 6:
        parts.append("</details>")
    parts.append("</section>")
    return "".join(parts)
