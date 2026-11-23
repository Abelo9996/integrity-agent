"""Compact, offline report presentation with progressive evidence disclosure."""

from __future__ import annotations

import html
import json
from collections import Counter
from urllib.parse import quote, urlsplit

from .models import FOOTER, stable_id
from .paper_review import CHECK_LABELS, QUEUES
from .report_summary import TIERS


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def finding_anchor(fid: str) -> str:
    return stable_id("result", fid)


def _finding(group, known_findings, known_works, known_artifacts):
    f = known_findings[group["representative_id"]]
    parts = [
        f'<details class="result" id="{finding_anchor(f["id"])}"><summary>'
        f'{esc(f["statement"])}</summary><div class="detail-body">',
        f'<p><span class="tier {esc(f["tier"])}">{TIERS[f["tier"]]}</span> '
        f"{esc(f['detector'])} · {len(group['finding_ids'])} tool result(s)</p>",
        '<p class="label">Linked work records</p><ul>',
    ]
    for wid in group["work_ids"]:
        w = known_works.get(wid)
        parts.append(f"<li>{esc(w['title'] if w else wid)}</li>")
    parts.append("</ul>")
    for evidence in f["evidence_files"]:
        parts.append(
            f'<img loading="lazy" src="{esc(quote(evidence, safe="/"))}" alt="Detector matched regions; expert review required">'
        )
    parts.append('<p class="label">What to check before interpreting this result</p><ul>')
    for limitation in f["limitations"]:
        parts.append(f"<li>{esc(limitation)}</li>")
    if not f["limitations"]:
        parts.append(
            "<li>Check the source, detector assumptions and possible benign explanations.</li>"
        )
    parts.append("</ul><details><summary>Sources, identifiers and measurements</summary><ul>")
    for aid in group["artifact_ids"]:
        a = known_artifacts[aid]
        url = a["url"] if urlsplit(a["url"]).scheme == "https" else ""
        link = f'<a href="{esc(url)}">{esc(a["source"])}</a>' if url else esc(a["source"])
        parts.append(f"<li>{link} · {esc(a['license'])}<br><code>{esc(aid)}</code></li>")
    parts.append("</ul><p>Finding IDs (unchanged detector outputs):</p><ul>")
    for fid in group["finding_ids"]:
        # Each raw ID has a reachable anchor even when equivalent evidence is grouped.
        anchor = "" if fid == f["id"] else f' id="{finding_anchor(fid)}"'
        parts.append(f"<li{anchor}><code>{esc(fid)}</code></li>")
    parts.append(
        "</ul><pre>"
        + esc(
            json.dumps({"parameters": f["parameters"], "measurements": f["measurements"]}, indent=2)
        )
        + "</pre></details></div></details>"
    )
    return "".join(parts)


def icon(name: str) -> str:
    paths = {
        "D1": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="1.5"/><path d="m4 17 5-5 4 4 3-3 5 5"/>',
        "D2": '<path d="M4 20h17M7 16V9m5 7V4m5 12v-5"/>',
        "D3": '<path d="M12 3v5M5 20V8h14v12M2 16h6m8 0h6"/>',
        "D4": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 9h16M4 15h16M10 9v12"/>',
        "D5": '<path d="M7 3h10l3 3v15H7zM7 7H3v14M11 11h5m-5 4h5"/>',
        "D6": '<rect x="3" y="4" width="12" height="14" rx="2"/><path d="M9 21h10a2 2 0 0 0 2-2V9M6 9h6m-6 4h4"/>',
        "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
        "shield": '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12h8"/>',
        "search": '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
    }
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + paths.get(name, paths["search"])
        + "</svg>"
    )


CELL_LABELS = {
    "signal": ("!", "Review signal"),
    "ran": ("●", "Check ran"),
    "partial": ("◐", "Partial check"),
    "failed": ("×", "Check failed"),
    "missing": ("—", "Not tested"),
}


def _dashboard(report):
    review = report["paper_review"]
    works = {w["id"]: w for w in report["works"]}
    findings = {f["id"]: f for f in report["findings"]}
    queues = review["queues"]
    check_events: dict[str, list[dict]] = {}
    for event in report["detector_coverage"]:
        check_events.setdefault(event["work_id"], []).append(event)
    signal_count = len(review["signal_work_ids"])
    tested = len(review["core_checked_work_ids"])
    actions = len(review["publication_action_work_ids"])
    retracted = len(review["retraction_work_ids"])
    retracted_tested = len(review["retraction_work_ids_with_core_checks"])
    action_label = (
        f"{retracted} linked to retractions · {retracted_tested} had image or data checks"
        if retracted
        else ""
    )
    parts = [
        '<section><div class="view overview" id="summary"><div class="queue-outcome">',
        f"<h2>{esc(review['title'])}</h2><p>{esc(review['explanation'])}</p></div>",
        '<div class="queue-metrics">',
        f'<a href="#queue-signals"><strong>{signal_count}</strong><span>Records with review signals</span></a>',
        f'<a href="#queue-notices"><strong>{actions}</strong><span>Records with publication actions</span><small>{esc(action_label)}</small></a>',
        f'<a href="#coverage-details"><strong>{tested}<small> / {len(works)}</small></strong><span>Records with image or data checks</span></a>',
        '</div><div class="section-heading"><h2 id="queue">Paper review</h2><a href="#results">All detector results</a></div>',
        '<div class="matrix-legend" aria-label="Coverage symbols">',
    ]
    for state, (symbol, label) in CELL_LABELS.items():
        parts.append(f'<span><b class="matrix-cell {state}">{symbol}</b> {label}</span>')
    parts.append("</div>")
    for key, label in QUEUES.items():
        rows = queues[key]
        parts.append(
            f'<details class="paper-queue" id="queue-{key}"><summary>{esc(label)} <span class="queue-count">{len(rows)}</span></summary>'
            '<div class="detail-body">'
        )
        if not rows:
            parts.append("<p>No linked records in this group.</p>")
        ordered = sorted(
            rows,
            key=lambda row: (
                not any(findings[fid]["tier"] == "strong" for fid in row["signal_ids"]),
                not row["core_checked"],
                -(works[row["work_id"]]["year"] or 0),
                works[row["work_id"]]["title"],
                row["work_id"],
            ),
        )
        for index, row in enumerate(ordered):
            if index == 5:
                parts.append(f"<details><summary>Show {len(ordered) - 5} more records</summary>")
            work = works[row["work_id"]]
            supporting = [findings[fid] for fid in row["signal_ids"] + row["notice_ids"]]
            tags = sorted(
                {
                    str(f["measurements"].get("type", "Publication update"))
                    for f in supporting
                    if f["kind"] == "publication-update"
                }
            )
            pills = "".join(
                f'<span class="paper-tag">{esc(tag.replace("-", " ").capitalize())}</span>'
                for tag in tags
            )
            anchor = stable_id("paper", work["id"])
            parts.append(
                f'<details class="paper-row" id="{anchor}"><summary><span class="paper-title">{esc(work["title"])}'
                f'<span class="paper-meta">{esc(work["year"] or "Year unavailable")} {pills}</span></span><span class="paper-cells">'
            )
            for detector, detector_label in CHECK_LABELS.items():
                state = row["cells"][detector]
                symbol, status = CELL_LABELS[state]
                parts.append(
                    f'<span class="paper-cell"><small>{detector_label}</small>'
                    f'<b class="matrix-cell {state}" role="img" aria-label="{status}" title="{status}">{symbol}</b></span>'
                )
            parts.append('</span></summary><div class="detail-body">')
            if work["doi"]:
                parts.append(
                    f'<p><a href="https://doi.org/{esc(quote(work["doi"], safe="/"))}">Open publication DOI</a></p>'
                )
            for f in supporting:
                title = (
                    ("Strong signal" if f["tier"] == "strong" else "Review signal")
                    if f["tier"] != "info"
                    else "Publication action"
                )
                parts.append(
                    f'<p><a href="#{finding_anchor(f["id"])}"><strong>{title}</strong> · {esc(f["statement"])}</a></p>'
                )
                doi = f["measurements"].get("notice_doi")
                if (
                    f["kind"] == "publication-update"
                    and isinstance(doi, str)
                    and doi.startswith("10.")
                ):
                    parts.append(
                        f'<p><a href="https://doi.org/{esc(quote(doi, safe="/"))}">Open publisher notice</a></p>'
                    )
                for evidence in f["evidence_files"][:1]:
                    parts.append(
                        f'<a class="evidence-preview" href="#{finding_anchor(f["id"])}"><img loading="lazy" src="{esc(quote(evidence, safe="/"))}" alt="Matched image regions"></a>'
                    )
            parts.append("<details><summary>Check details and missing inputs</summary><ul>")
            for event in check_events.get(work["id"], []):
                parts.append(
                    f"<li>{esc(event['detector'])} · {esc(event['check'])} · {esc(event['status'])} · {esc(event['detail'])}</li>"
                )
            parts.append("</ul></details>")
            parts.append("</div></details>")
        if len(ordered) > 5:
            parts.append("</details>")
        parts.append("</div></details>")
    return "".join(parts) + "</div></section>"


def _coverage_details(report):
    works = {w["id"] for w in report["works"]}
    parts = [
        '<div id="coverage-details"><h2>Checks and missing inputs</h2>'
        "<p>Each count includes records with at least one completed check. PDF image checks use embedded images. Vector plots and underlying data require separate review.</p>"
    ]
    for row in report["reading_summary"]["detector_coverage"]:
        parts.append(
            f'<details id="check-{row["detector"]}"><summary>{esc(row["label"])} · {row["works_with_completed_check"]} / {len(works)} records</summary><div class="detail-body">'
        )
        checks = sorted(
            {c["check"] for c in report["detector_coverage"] if c["detector"] == row["detector"]}
        )
        for check in checks:
            events = [
                c
                for c in report["detector_coverage"]
                if c["detector"] == row["detector"]
                and c["check"] == check
                and c["work_id"] in works
            ]
            n_ran = len({c["work_id"] for c in events if c["status"] == "ran"})
            n_failed = len({c["work_id"] for c in events if c["status"] == "failed"})
            parts.append(
                f"<h3>{esc(check)}</h3><p>{n_ran} records checked · {n_failed} had failures</p><ul>"
            )
            reasons = Counter(c["detail"] for c in events if c["status"] != "ran")
            parts.extend(
                f"<li>{count} × {esc(reason)}</li>" for reason, count in sorted(reasons.items())
            )
            parts.append("</ul>")
        if not checks:
            parts.append("<p>No completed check is recorded.</p>")
        parts.append("</div></details>")
    return "".join(parts) + "</div>"


def render_report(report: dict) -> str:
    brief = report["reading_summary"]
    author = report["author"]
    works = {w["id"]: w for w in report["works"]}
    artifacts = {a["artifact_id"]: a for a in report["artifacts"]}
    findings = {f["id"]: f for f in report["findings"]}
    rejected = report["verification"]["rejected"]
    profile = report["review"].get("image_profile", "not recorded")
    parts = [
        '<a class="skip-link" href="#summary">Skip to run outcome</a>',
        '<div class="brand-bar"><span class="brand">'
        + icon("shield")
        + ' INTEGRITY <span>Evidence review</span></span><span class="private-label">Private report</span></div>',
        '<header><div><p class="eyebrow">Researcher test run</p>',
        f'<h1>{esc(author["name"])}</h1></div><span class="header-note"><a href="summary.svg">Open one-page visual summary ↗</a><br>Human interpretation required</span></header>',
        '<nav aria-label="Report views"><a data-view="summary" href="#summary">Paper review</a><a data-view="results" href="#results">Evidence library</a><a data-view="audit" href="#audit">Coverage &amp; sources</a></nav>',
    ]
    if rejected:
        reasons = Counter(item["reason"] for item in rejected)
        parts.append(
            f'<aside class="warning"><h2>Verification gaps</h2><p>{len(rejected)} claims were excluded from all counts.</p><ul>'
            + "".join(f"<li>{esc(reason)}: {count}</li>" for reason, count in reasons.items())
            + '</ul><a href="verifier-log.json">View rejected IDs and reasons</a></aside>'
        )
    notes = [
        c["detail"]
        for c in report["coverage"]
        if c["work_id"] == author["id"] and c["status"] == "skipped"
    ]
    if notes:
        parts.append(
            '<aside class="warning"><h2>Scope of this run</h2><ul>'
            + "".join(f"<li>{esc(n)}</li>" for n in notes)
            + "</ul></aside>"
        )
    if profile == "experimental-compression":
        parts.append(
            '<aside class="warning"><h2>Experimental image search</h2><p>This profile misses more small smooth copies in regression tests. Its sensitivity is not established.</p></aside>'
        )
    parts.append(_dashboard(report))
    parts.append(
        '<section><div class="view" id="results"><div class="section-heading"><div><p class="eyebrow">Source-linked detector outputs</p><h2>Evidence library</h2></div>'
        '<a href="#summary">Back to overview</a></div>'
        '<p class="view-intro">Open a category to inspect exact statements, sources and limitations. Result counts are not independent issue counts.</p>'
    )
    for row in brief["categories"]:
        parts.append(
            f'<details class="category" id="{row["id"]}"><summary>{icon(row["detector"])}<span>{esc(row["label"])}</span>'
            f'<span class="tier {row["tier"]}">{TIERS[row["tier"]]}</span><span class="category-count">{row["result_count"]} results</span></summary>'
            f'<div class="detail-body"><p>{esc(row["explanation"])}</p>'
        )
        notice_count = len(row.get("notice_title_finding_ids", []))
        if notice_count:
            parts.append(
                f"<p>{notice_count} of {row['result_count']} text matches involve records with notice-style titles; shared wording may explain them.</p>"
            )
        for status, ids in row.get("status_work_ids", {}).items():
            parts.append(
                f"<p>{esc(status.capitalize())} metadata: {len(ids)} linked work records.</p>"
            )
        for group in report["review_groups"]:
            if group["representative_id"] in row["finding_ids"]:
                parts.append(_finding(group, findings, works, artifacts))
        parts.append("</div></details>")
    parts.append(
        '<p class="verification-note">Verified = source references and file hashes checked. It does not mean expert-confirmed.</p></div></section>'
    )
    parts.append(
        '<section><div class="view" id="audit"><div class="section-heading"><div><p class="eyebrow">Limits and provenance</p><h2>Coverage &amp; sources</h2></div><a href="#summary">Back to overview</a></div>'
    )
    parts.append(_coverage_details(report))
    parts.append(
        '<details id="technical"><summary>Collection log and technical details</summary><div class="detail-body">'
        f"<p>{report['summary']['works_attempted']} works attempted; {len(artifacts)} artifacts collected. Image search profile: {esc(profile)}.</p>"
    )
    attempts = brief["collection_attempts"]
    parts.append(
        f"<p>{attempts.get('ok', 0)} successful, {attempts.get('skipped', 0)} skipped and {attempts.get('failed', 0)} failed source attempts; not unique-paper counts.</p><ul>"
    )
    logs = Counter((c["source"], c["status"], c["detail"]) for c in report["coverage"])
    parts.extend(
        f"<li>{count} × {esc(source)} · {esc(status)}: {esc(detail)}</li>"
        for (source, status, detail), count in sorted(logs.items())
    )
    parts.append(
        '</ul></div></details><p><a href="summary.svg">One-page visual summary</a> · <a href="report.json">Complete evidence JSON</a> · <a href="verifier-log.json">Verification log</a></p></div></section>'
        f"<footer>{icon('shield')}<span>{FOOTER}</span></footer>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Evidence review — "
        + esc(author["name"])
        + "</title><style>"
        + CSS
        + "</style></head><body><main>"
        + "".join(parts)
        + "</main><script>"
        + SCRIPT
        + "</script></body></html>"
    )


CSS = """
:root{color-scheme:light;--bg:#f5f5f2;--paper:#fff;--ink:#172f36;--muted:#566970;--line:#dce4e3;--teal:#145d68;--teal-soft:#e9f2f2;--amber:#8a530d;--amber-soft:#fff2db;--purple:#625092;--shadow:0 4px 20px #18323a05}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1220px;margin:auto;padding:0 40px 28px}
a{color:var(--teal);text-underline-offset:4px}
a:hover{text-decoration-thickness:2px}
svg{width:24px;height:24px;flex-shrink:0}
h1,h2,h3,p{margin:0}
h1,h2,h3{letter-spacing:-.03em}
h1{font-size:30px;font-weight:650;line-height:1.2}
h2{font-size:23px;font-weight:650;line-height:1.25}
h3{font-size:17px;line-height:1.35}
p{line-height:1.55}
.brand-bar{height:74px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.brand{display:flex;gap:10px;align-items:center;letter-spacing:.12em;font-size:12px;font-weight:750}
.brand>span{border-left:1px solid #b8c8cb;padding-left:12px;color:var(--muted);font-weight:500;letter-spacing:0}
.private-label{font-size:12px;color:var(--muted);border:1px solid #cbd5d4;padding:5px 10px;border-radius:5px}
header{display:flex;align-items:center;justify-content:space-between;padding:30px 0 24px}
.eyebrow{font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:750;color:var(--muted);margin-bottom:8px}
.header-note{font-size:12px;line-height:1.6;color:var(--muted);text-align:right}
nav{display:flex;gap:28px;border-bottom:1px solid var(--line);margin-bottom:28px}
nav a{min-height:46px;padding:10px 0 12px;text-decoration:none;font-size:14px;font-weight:600;color:var(--muted);border-bottom:3px solid transparent}
nav a[aria-current=page]{border-color:var(--teal);color:var(--ink)}
section{margin:0}
[hidden]{display:none!important}
.view{scroll-margin-top:20px}
.section-heading{display:flex;justify-content:space-between;align-items:end;gap:16px;margin:30px 0 16px}
.section-heading>a{display:flex;align-items:center;gap:8px;font-size:12px;min-height:44px;text-decoration:none}
.section-heading>a svg{width:18px}
.evidence-preview{display:block;background:#f4f5f5;border-radius:6px;margin-bottom:16px;overflow:hidden}
.evidence-preview img{width:100%;max-height:190px;object-fit:contain;display:block}
.view-intro,.verification-note{color:var(--muted);font-size:14px;margin:16px 0 24px}
.warning{padding:18px 22px;margin:0 0 22px;border:1px solid #e3bf88;background:var(--amber-soft);border-radius:10px}
.warning p{margin-top:8px}
.warning h2{font-size:18px}
details{background:var(--paper);border:1px solid var(--line);border-radius:9px;margin:12px 0}
summary{cursor:pointer;padding:16px;font-size:14px;font-weight:600;min-height:48px}
summary:hover{background:#f1f7f7}
.category>summary{display:flex;gap:12px;align-items:center}
.category>summary:before{content:'+';font-size:18px;font-weight:400}
.category[open]>summary:before{content:'−'}
.category-count{margin-left:auto;white-space:nowrap;font-size:12px;color:var(--muted)}
.detail-body{padding:8px 20px 20px}
.detail-body>p,.detail-body>h3{margin:12px 0}
.detail-body li{font-size:14px;margin:6px 0}
.detail-body ul{padding-left:20px}
.detail-body p{font-size:14px}
.detail-body details>ul,.detail-body details>pre{margin:12px 20px 20px}
.tier{font-size:10px;border-radius:4px;padding:4px 7px;background:var(--teal-soft);color:var(--teal);white-space:nowrap}
.tier.review,.tier.strong{background:var(--amber-soft);color:var(--amber)}
pre{background:#f1f4f4;padding:16px;font-size:12px;white-space:pre-wrap}
img{max-width:100%;height:auto}
code,a,li,pre{overflow-wrap:anywhere}
footer{display:flex;align-items:center;gap:9px;font-size:11px;line-height:1.4;color:var(--muted);margin-top:30px;padding-top:20px;border-top:1px solid var(--line)}
footer svg{width:16px;height:16px}
.skip-link{position:absolute;left:12px;top:-70px;padding:12px;background:var(--paper);z-index:3}
.skip-link:focus{top:8px}
a:focus-visible,summary:focus-visible{outline:3px solid #387b89;outline-offset:4px}
.label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:650;color:var(--muted)}
.queue-outcome {
    padding: 24px;
    background: #fff7eb;
    border: 1px solid #e9d3b7;
    border-radius: 12px;
}
.queue-outcome h2 { font-size: clamp(23px, 3vw, 34px); }
.queue-outcome p { margin-top: 8px; color: #5f4b31; }
.queue-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.queue-metrics a {
    background: white;
    padding: 16px;
    border-radius: 10px;
    border: 1px solid var(--line);
    color: var(--ink);
    text-decoration: none;
}
.queue-metrics a:hover { border-color: var(--teal); }
.queue-metrics strong { display: block; font-size: clamp(28px, 4vw, 42px); line-height: 1.2; }
.queue-metrics small { color: var(--muted); font-size: .52em; font-weight: 500; }
.queue-metrics a > small { display: block; font-size: .75rem; margin-top: 3px; }
.queue-metrics span { display: block; margin-top: 6px; color: var(--muted); font-size: .9rem; }
.matrix-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; font-size: .8rem; color: var(--muted); }
.matrix-legend span { display: inline-flex; align-items: center; gap: 6px; }
.matrix-cell { display: inline-grid; width: 22px; height: 22px; place-items: center; border-radius: 5px; color: #41545c; background: #edf0f1; }
.matrix-cell.signal { color: #853820; background: #f9e2d7; }
.matrix-cell.ran { color: #145d68; background: #dceef0; }
.matrix-cell.failed, .matrix-cell.partial { color: #804c10; background: #ffedd5; }
.queue-count { float: right; border-radius: 99px; background: var(--teal-soft); padding: 0 10px; }
.paper-row { margin: 6px 0; }
.paper-row > summary { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16px; align-items: center; }
.paper-row > summary::-webkit-details-marker { display: none; }
.paper-title { min-width: 0; overflow-wrap: anywhere; }
.paper-title::before { content: "›"; margin-right: .45em; color: var(--teal); }
.paper-row[open] .paper-title::before { content: "⌄"; }
.paper-meta { display: block; margin-top: 4px; font-size: .77rem; color: var(--muted); }
.paper-tag { background: #ede8f4; color: #523e64; border-radius: 4px; margin-left: 6px; padding: 2px 6px; }
.paper-cells { display: grid; grid-template-columns: repeat(6, minmax(34px, 1fr)); gap: 8px; }
.paper-cell { display: grid; justify-items: center; gap: 4px; color: var(--muted); }
.paper-cell small { font-size: .67rem; }
@media (max-width: 650px) {
    main { padding: 0 16px 24px; }
    .brand-bar { height: 56px; }
    header { padding: 20px 0; gap: 10px; }
    h1 { font-size: 24px; }
    nav { gap: 14px; }
    nav a { font-size: .8rem; }
    .queue-outcome { padding: 16px; }
    .queue-metrics { gap: 6px; }
    .queue-metrics a { padding: 8px; }
    .queue-metrics span { font-size: .73rem; }
    .paper-row > summary { grid-template-columns: minmax(0, 1fr); }
    .paper-cells { max-width: 270px; }
    .detail-body { padding: 8px 12px 12px; }
    .category > summary { flex-wrap: wrap; }
}

"""

# No external dependencies; fragments open the correct view and its evidence disclosures.
SCRIPT = """
document.querySelector('.paper-queue:has(.paper-row)')?.setAttribute('open','');
function showView(view){
  document.querySelectorAll('.view').forEach(item=>{item.hidden=item!==view;});
  document.querySelectorAll('nav a[data-view]').forEach(link=>{
    if(link.dataset.view===view.id)link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });
}
function revealHash(){
  let id;
  try{id=decodeURIComponent(location.hash.slice(1));}catch(_){id='summary';}
  const target=document.getElementById(id)||document.getElementById('summary');
  const view=target.closest('.view');
  if(!view)return;
  showView(view);
  let node=target;
  while(node){if(node.tagName==='DETAILS')node.open=true;node=node.parentElement;}
  if(location.hash)target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange',revealHash);
document.addEventListener('DOMContentLoaded',revealHash);
document.addEventListener('click',event=>{
  const link=event.target.closest('a[href^="#"]');
  if(link&&link.hash===location.hash)revealHash();
});
"""
