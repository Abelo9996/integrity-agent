"""One-page visual export of the paper review dashboard."""

from __future__ import annotations

import html
import json
import textwrap


def render_snapshot(report: dict) -> str:
    review = report["paper_review"]
    total = len(report["works"])
    flagged = len(report["file_review"]["flagged_files"])
    headline = f"{flagged} detector input {'file' if flagged == 1 else 'files'} flagged"
    retractions = len(review["retraction_work_ids"])
    retraction_checks = len(review["retraction_work_ids_with_core_checks"])
    explanation = (
        f"{retraction_checks} of {retractions} retraction-linked records received image or data checks."
        if retractions
        else review["explanation"]
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title">',
        f'<title id="title">{html.escape(headline)}</title>',
        "<metadata>" + html.escape(json.dumps(report["reading_summary"])) + "</metadata>",
        '<rect width="1200" height="630" fill="#f5f5f2"/>',
    ]

    def rect(x, y, width, height, fill="white", stroke="#dce4e3", radius=12):
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
        )

    def text(x, y, value, size=16, fill="#172f36", weight=400, width=80, line=22):
        for i, content in enumerate(textwrap.wrap(str(value), width=width)):
            parts.append(
                f'<text x="{x}" y="{y + i * line}" font-family="Helvetica,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(content)}</text>'
            )

    text(42, 36, "PRIVATE EVIDENCE REVIEW", 12, "#566970", 700)
    text(42, 76, report["author"]["name"], 27, weight=700, width=75)
    rect(42, 103, 1116, 114, "#fff7eb", "#e9d3b7")
    text(62, 150, headline, 31, weight=700, width=68, line=34)
    text(62, 190, explanation, 16, "#5f4b31", width=116)
    metrics = [
        (flagged, "Flagged detector input files", "files-flagged"),
        (
            len(review["publication_action_work_ids"]),
            "Records with publication actions",
            "files-notices",
        ),
        (
            len(report["file_review"]["checked_files"]),
            "Source files used for checks",
            "files-checked",
        ),
    ]
    for i, (value, label, target) in enumerate(metrics):
        x = 42 + i * 376
        rect(x, 232, 364, 111)
        text(x + 18, 279, value, 37, weight=700)
        text(x + 18, 315, label, 15, "#566970")
        if target == "files-notices" and review["retraction_work_ids"]:
            retracted = len(review["retraction_work_ids"])
            tested = len(review["retraction_work_ids_with_core_checks"])
            text(
                x + 18,
                333,
                f"{retracted} linked to retractions · {tested} had image or data checks",
                12,
                "#566970",
            )
        parts.append(
            f'<a href="report.html#{target}" aria-label="{label}"><rect x="{x}" y="232" width="364" height="111" fill="transparent"/></a>'
        )

    text(42, 387, "Image and data check coverage", 22, weight=700)
    comparisons = [
        ("All publication records", len(review["core_checked_work_ids"]), total),
        (
            "Retraction-linked records",
            len(review["retraction_work_ids_with_core_checks"]),
            len(review["retraction_work_ids"]),
        ),
    ]
    for offset, (label, count, population) in enumerate(comparisons):
        y = 421 + offset * 51
        text(42, y, label, 15, weight=600)
        text(1060, y, f"{count} / {population}", 14, "#566970")
        rect(42, y + 9, 1116, 9, "#e4e9e9", "#e4e9e9", radius=3)
        if count and population:
            rect(42, y + 9, 1116 * count / population, 9, "#145d68", "#145d68", radius=3)
    rejected = len(report["verification"]["rejected"])
    if rejected:
        text(42, 537, f"Verification gaps: {rejected} claims excluded.", 13, "#8a530d", 700)
    text(
        42,
        566,
        "Open report.html for filenames, detector evidence and publisher notices.",
        15,
        "#145d68",
        600,
    )
    text(42, 598, report["footer"], 12, "#566970", width=140)
    parts.append("</svg>")
    return "".join(parts)
