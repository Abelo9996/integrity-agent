"""One-page vector summary of the same verified data shown in the dashboard."""

from __future__ import annotations

import html
import json
import textwrap


def render_snapshot(report: dict) -> str:
    brief = report["reading_summary"]
    collection, outcome = brief["collection"], brief["outcome"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1000" viewBox="0 0 1400 1000" role="img" aria-labelledby="title description">',
        f'<title id="title">{html.escape(outcome["title"])}</title>',
        '<desc id="description">Run outcome, source counts, evidence categories and completed-check coverage. Open the HTML report for source evidence.</desc>',
        "<metadata>" + html.escape(json.dumps(brief)) + "</metadata>",
        '<rect width="1400" height="1000" fill="#f5f5f2"/>',
    ]

    def rect(x, y, width, height, fill="white", stroke="#dce4e3", radius=12):
        parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
        )

    def text(x, y, value, size=16, fill="#172f36", weight=400, width=70, line=22):
        lines = textwrap.wrap(str(value), width=width) or [""]
        for i, content in enumerate(lines):
            parts.append(
                f'<text x="{x}" y="{y + i * line}" font-family="Helvetica,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(content)}</text>'
            )

    text(64, 42, "INTEGRITY  /  EVIDENCE REVIEW", 12, "#566970", 700)
    text(64, 96, report["author"]["name"], 30, weight=700, width=70, line=34)
    text(1200, 42, "PRIVATE REPORT", 11, "#566970", 600)
    rejected = len(report["verification"]["rejected"])
    if rejected:
        text(
            64,
            117,
            f"Verification gaps: {rejected} claims excluded. Review the HTML verification log.",
            12,
            "#8a530d",
            600,
            width=150,
        )
    rect(64, 126, 1272, 256)
    rect(88, 149, 290, 27, "#fff2db", "#f1dcb6", 5)
    text(99, 167, outcome["label"].upper(), 11, "#8a530d", 600)
    text(88, 220, outcome["title"], 34, weight=700, width=37, line=39)
    text(88, 314, outcome["explanation"], 15, "#566970", width=80, line=21)
    parts.append('<path d="M847 158v192" stroke="#dce4e3"/>')
    steps = [
        (collection["publication_record_count"], "publication records in scope"),
        (len(collection["document_artifact_ids"]), "document files retrieved"),
        (len(collection["core_checked_work_ids"]), "records with image / data checks"),
    ]
    for i, (n, label) in enumerate(steps):
        y = 189 + i * 70
        text(878, y, n, 29, weight=700)
        text(963, y, label, 14, width=34, line=19)
        if i < 2:
            parts.append(f'<path d="M893 {y + 12}v28" stroke="#a9bec2" stroke-dasharray="3 4"/>')
    text(878, 362, "Different units; not a conversion rate.", 10, "#566970")
    text(64, 426, "Evidence at a glance", 23, weight=700)
    cards = brief["cards"][:3]
    if len(brief["cards"]) > 3:
        text(1050, 426, f"First 3 of {len(brief['cards'])} categories", 12, "#566970")
    for i, card in enumerate(cards):
        x = 64 + i * 432
        rect(x, 448, 408, 222)
        parts.append("<g>")
        text(x + 22, 477, card["badge"].upper(), 11, "#566970", 600)
        text(x + 22, 528, card["metric"], 45, weight=700)
        text(x + 22, 556, card["label"], 18, weight=600, width=37, line=22)
        text(x + 22, 610, card["note"], 14, "#566970", width=49, line=19)
        text(x + 22, 651, "Inspect evidence →", 12, "#145d68", 700)
        parts.append("</g>")
        parts.append(
            f'<a href="report.html#{card["category_id"]}"><rect x="{x}" y="448" width="408" height="222" fill="transparent"/></a>'
        )
    if not cards:
        rect(64, 448, 1272, 150)
        text(90, 493, "No accepted detector results are available.", 22, weight=600)
        text(
            90,
            534,
            "Check missing inputs and verification errors before interpreting this absence.",
            16,
            "#566970",
            width=110,
        )
    text(64, 712, "What was tested?", 23, weight=700)
    labels = [
        "Images",
        "Summary stats",
        "Trial baselines",
        "Raw data",
        "Publication records",
        "Text",
    ]
    for i, (row, label) in enumerate(zip(brief["detector_coverage"], labels, strict=True)):
        x = 64 + i * 214
        n = row["works_with_completed_check"]
        failed = bool(row["work_ids_with_failed_check"])
        rect(x, 734, 202, 104)
        state = "Some checks ran" if n else "Check failed" if failed else "Not tested"
        text(x + 14, 758, state, 11, "#145d68" if n else "#8a530d", 600)
        text(x + 14, 786, label, 14, weight=600)
        text(x + 14, 816, f"{n} / {collection['publication_record_count']} records", 13, "#566970")
    text(
        64,
        861,
        "A record counts when at least one check completed. Missing checks do not establish a clean result.",
        12,
        "#566970",
        width=150,
    )
    text(64, 901, "NEXT STEP", 10, "#566970", 700)
    text(64, 925, outcome["next_step"], 16, width=140)
    text(64, 969, report["footer"], 12, "#566970", width=170)
    parts.append("</svg>")
    return "".join(parts)
