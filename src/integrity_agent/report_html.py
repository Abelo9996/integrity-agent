"""Compact, offline report presentation with progressive evidence disclosure."""

from __future__ import annotations

import html
import json
from collections import Counter
from urllib.parse import quote, urlsplit

from .models import FOOTER, stable_id
from .report_summary import TIER_ORDER, TIERS


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


def _dashboard(report):
    brief = report["reading_summary"]
    outcome, collection = brief["outcome"], brief["collection"]
    total = collection["publication_record_count"]
    n_docs = len(collection["document_artifact_ids"])
    n_notices = len(collection["notice_title_document_ids"])
    parts = [
        '<section><div class="view overview" id="summary">',
        '<div class="outcome-grid"><div class="outcome">',
        f'<span class="status {esc(outcome["state"])}">{icon("shield")}{esc(outcome["label"])}</span>',
        '<p class="eyebrow">Outcome of this test run</p>',
        f'<h2>{esc(outcome["title"])}</h2><p class="outcome-copy">{esc(outcome["explanation"])}</p>',
        '<a class="primary-link" href="#coverage">See what was tested ' + icon("arrow") + "</a>",
        '</div><div class="run-path" aria-label="Collection and assessment counts; different units, not a conversion rate">',
    ]
    doc_note = "Downloaded files, not necessarily research papers"
    if n_docs and n_docs == n_notices:
        doc_note = "All linked to records with notice-style titles"
    steps = [
        (
            str(total),
            "publication records",
            "Papers, notices and versions can appear separately",
            "D5",
        ),
        (str(n_docs), "document files retrieved", doc_note, "D6"),
        (
            str(len(collection["core_checked_work_ids"])),
            "records with image / data checks",
            "At least one completed image, statistics or raw-data check",
            "D1",
        ),
    ]
    for i, (value, title, note, symbol) in enumerate(steps):
        parts.append(
            f'<div class="path-step"><span class="path-icon">{icon(symbol)}</span>'
            f'<div><div class="path-title"><strong>{value}</strong> {esc(title)}</div>'
            f'<span class="path-note">{esc(note)}</span></div></div>'
        )
        if i < len(steps) - 1:
            parts.append('<div class="path-connector" aria-hidden="true"></div>')
    parts.append(
        '</div></div><div class="section-heading"><div><p class="eyebrow">What came back</p>'
        '<h2>Evidence at a glance</h2></div><a href="#results">Open evidence library '
        + icon("arrow")
        + "</a></div>"
    )
    cards = brief["cards"]
    parts.append('<div class="evidence-cards">')
    for card in cards[:3]:
        row = next(r for r in brief["categories"] if r["id"] == card["category_id"])
        supporting = [f for f in report["findings"] if f["id"] in card["finding_ids"]]
        preview = next((path for f in supporting for path in f["evidence_files"]), None)
        parts.append(
            f'<article class="evidence-card {esc(card["tier"])}">'
            f'<div class="card-top"><span class="card-icon">{icon(row["detector"])}</span><span class="card-tag">{esc(card["badge"])}</span></div>'
        )
        if preview:
            parts.append(
                f'<a class="evidence-preview" href="#{card["category_id"]}"><img src="{esc(quote(preview, safe="/"))}" alt="Matched image regions from verified detector evidence"></a>'
            )
        parts.append(
            f'<strong class="card-metric">{esc(card["metric"])}</strong><h3>{esc(card["label"])}</h3>'
            f'<p>{esc(card["note"])}</p><a class="card-action" href="#{card["category_id"]}">Inspect evidence {icon("arrow")}</a></article>'
        )
    if not cards:
        parts.append(
            '<div class="empty-card">'
            + icon("search")
            + "<h3>No accepted detector results are available.</h3><p>Use the coverage map to see what was left untested.</p></div>"
        )
    parts.append("</div>")
    if len(cards) > 3:
        parts.append(
            f'<p class="additional"><a href="#results">See all {len(cards)} result categories</a> — the cards show the first three in review priority order.</p>'
        )
    parts.append(
        '<div class="section-heading" id="coverage"><div><p class="eyebrow">Scope of the test</p><h2>What was tested?</h2></div>'
        '<span class="map-legend"><span class="legend-dot"></span> Some checks ran <span class="legend-hatch"></span> Not tested</span></div>'
        '<div class="coverage-map">'
    )
    short_labels = {
        "D1": "Images",
        "D2": "Summary statistics",
        "D3": "Trial baselines",
        "D4": "Raw data",
        "D5": "Publication records",
        "D6": "Text",
    }
    for row in brief["detector_coverage"]:
        ran = row["works_with_completed_check"]
        failed = len(row["work_ids_with_failed_check"])
        status = "Some checks ran" if ran else "Check failed" if failed else "Not tested"
        percent = 100 * ran / total if total else 0
        parts.append(
            f'<a class="coverage-tile {"ran" if ran else "unassessed"}" href="#check-{row["detector"]}">'
            f'<span class="tile-top">{icon(row["detector"])}<span>{esc(status)}</span></span>'
            f'<h3>{short_labels[row["detector"]]}</h3><div class="coverage-bar" aria-hidden="true"><span style="width:{percent:.3f}%"></span></div>'
            f'<div class="tile-count"><strong>{ran}</strong> / {total} records</div>'
        )
        if failed:
            parts.append(
                f'<span class="failed-note">{failed} record(s) also had failed checks</span>'
            )
        parts.append("</a>")
    parts.append(
        '</div><p class="coverage-caption">Counts show records with at least one completed check. This does not mean every check ran. No completed check is not a clean result.</p>'
        '<div class="next-step"><span class="next-icon">'
        + icon("arrow")
        + '</span><div><p class="eyebrow">The next useful step</p>'
        f'<p>{esc(outcome["next_step"])}</p></div><a href="#audit">View missing inputs</a></div></div></section>'
    )
    return "".join(parts)


def _coverage_details(report):
    works = {w["id"] for w in report["works"]}
    parts = ['<div id="coverage-details"><h2>Checks and missing inputs</h2>']
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
        '<nav aria-label="Report views"><a data-view="summary" href="#summary">Run overview</a><a data-view="results" href="#results">Evidence library</a><a data-view="audit" href="#audit">Coverage &amp; sources</a></nav>',
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
        f'<details id="papers"><summary>Browse {len(works)} publication records</summary><div class="detail-body">'
    )
    for w in sorted(works.values(), key=lambda w: (-(w["year"] or 0), w["title"])):
        fs = [f for f in findings.values() if w["id"] in f["work_ids"]]
        parts.append(
            f'<details><summary>{esc(w["title"])} · {len(fs)} result(s)</summary><div class="detail-body">'
            f"<p>{esc(w['year'] or 'Year unavailable')} · {esc(w['venue'])}</p><ul>"
        )
        for f in sorted(fs, key=lambda f: TIER_ORDER[f["tier"]]):
            parts.append(
                f'<li><a href="#{finding_anchor(f["id"])}">{esc(TIERS[f["tier"]])}: {esc(f["statement"])}</a></li>'
            )
        parts.append("</ul><details><summary>Individual checks and reasons</summary><ul>")
        for c in report["detector_coverage"]:
            if c["work_id"] == w["id"]:
                parts.append(
                    f"<li>{esc(c['detector'])} / {esc(c['check'])}: {esc(c['status'])} · {esc(c['detail'])}</li>"
                )
        parts.append("</ul></details></div></details>")
    parts.append(
        '</div></details><details id="technical"><summary>Collection log and technical details</summary><div class="detail-body">'
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
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1220px;margin:auto;padding:0 40px 28px}
a{color:var(--teal);text-underline-offset:4px}a:hover{text-decoration-thickness:2px}svg{width:24px;height:24px;flex-shrink:0}h1,h2,h3,p{margin:0}h1,h2,h3{letter-spacing:-.03em}h1{font-size:30px;font-weight:650;line-height:1.2}h2{font-size:23px;font-weight:650;line-height:1.25}h3{font-size:17px;line-height:1.35}p{line-height:1.55}.brand-bar{height:74px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}.brand{display:flex;gap:10px;align-items:center;letter-spacing:.12em;font-size:12px;font-weight:750}.brand>span{border-left:1px solid #b8c8cb;padding-left:12px;color:var(--muted);font-weight:500;letter-spacing:0}.private-label{font-size:12px;color:var(--muted);border:1px solid #cbd5d4;padding:5px 10px;border-radius:5px}
header{display:flex;align-items:center;justify-content:space-between;padding:30px 0 24px}.eyebrow{font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:750;color:var(--muted);margin-bottom:8px}.header-note{font-size:12px;line-height:1.6;color:var(--muted);text-align:right}nav{display:flex;gap:28px;border-bottom:1px solid var(--line);margin-bottom:28px}nav a{min-height:46px;padding:10px 0 12px;text-decoration:none;font-size:14px;font-weight:600;color:var(--muted);border-bottom:3px solid transparent}nav a[aria-current=page]{border-color:var(--teal);color:var(--ink)}section{margin:0}[hidden]{display:none!important}.view{scroll-margin-top:20px}.outcome-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:28px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:30px;box-shadow:var(--shadow)}.status{display:inline-flex;align-items:center;gap:7px;color:var(--amber);background:var(--amber-soft);border:1px solid #f1dcb6;border-radius:5px;padding:5px 9px;font-size:11px;font-weight:650;margin-bottom:21px}.status svg{width:16px;height:16px}.status.review_required{color:#8e3924;background:#fff0e8;border-color:#eec6b8}.status.no_priority_signals{color:var(--teal);background:var(--teal-soft);border-color:#c3dfe2}.outcome h2{font-size:35px;line-height:1.12;max-width:490px}.outcome-copy{font-size:14px;color:var(--muted);max-width:480px;margin:15px 0 18px}.primary-link{display:inline-flex;gap:9px;align-items:center;font-size:13px;font-weight:650;min-height:44px;text-decoration:none}.primary-link svg{width:19px}.run-path{border-left:1px solid var(--line);padding-left:28px;align-self:center}.path-step{display:flex;align-items:center;gap:15px}.path-icon{display:flex;align-items:center;justify-content:center;width:42px;height:42px;flex-shrink:0;border-radius:10px;background:var(--teal-soft);color:var(--teal)}.path-step:last-child .path-icon{color:var(--amber);background:var(--amber-soft)}.path-title{font-size:13px;line-height:1.4}.path-title strong{font-size:27px;font-variant-numeric:tabular-nums;margin-right:4px}.path-note{display:block;font-size:11px;color:var(--muted);max-width:280px;margin-top:2px}.path-connector{border-left:1px dashed #a8b9bd;height:20px;margin-left:21px}
.section-heading{display:flex;justify-content:space-between;align-items:end;gap:16px;margin:30px 0 16px}.section-heading>a{display:flex;align-items:center;gap:8px;font-size:12px;min-height:44px;text-decoration:none}.section-heading>a svg{width:18px}.evidence-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.evidence-card{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px;box-shadow:var(--shadow);display:flex;flex-direction:column}.card-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:16px}.card-icon{color:var(--teal);display:flex}.card-tag{font-size:10px;letter-spacing:.035em;color:var(--muted);background:#f0f4f4;border-radius:4px;padding:4px 6px}.card-metric{font-size:42px;line-height:1;font-weight:600;letter-spacing:-.06em;margin-bottom:8px}.evidence-card h3{max-width:260px;font-size:17px}.evidence-card p{font-size:12px;line-height:1.5;color:var(--muted);margin:9px 0 14px;max-width:270px}.card-action{display:flex;align-items:center;justify-content:space-between;font-size:12px;font-weight:650;text-decoration:none;min-height:44px;margin-top:auto;border-top:1px solid #edf0ef;padding-top:9px}.card-action svg{width:18px}.evidence-card.review,.evidence-card.strong{border-top:3px solid #a5633d}.evidence-preview{display:block;background:#f4f5f5;border-radius:6px;margin-bottom:16px;overflow:hidden}.evidence-preview img{width:100%;max-height:190px;object-fit:contain;display:block}.empty-card{grid-column:1/-1;border:1px dashed #a9bcbf;padding:24px;border-radius:10px;display:grid;gap:8px}.empty-card p{color:var(--muted)}.additional{font-size:13px;color:var(--muted);margin-top:12px}
.coverage-map{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.coverage-tile{border:1px solid var(--line);border-radius:9px;background:var(--paper);padding:13px 12px;text-decoration:none;color:var(--ink)}.coverage-tile:hover{border-color:#6e969c;box-shadow:0 3px 12px #17353e0a}.tile-top{display:flex;align-items:center;justify-content:space-between;gap:5px;color:var(--muted);font-size:9px;white-space:nowrap}.tile-top svg{width:19px;height:19px}.unassessed .tile-top{color:var(--amber)}.ran .tile-top{color:var(--teal)}.coverage-tile h3{font-size:12px;letter-spacing:0;margin:12px 0 13px;min-height:16px}.coverage-bar{height:5px;border-radius:4px;overflow:hidden;background:#e9eeef}.coverage-bar span{display:block;height:100%;background:var(--teal);border-radius:4px}.unassessed .coverage-bar{background:repeating-linear-gradient(120deg,#e5d9c7 0 2px,#f8f2e8 2px 5px)}.tile-count{font-size:10px;margin-top:10px;color:var(--muted)}.tile-count strong{font-size:16px;color:var(--ink);font-weight:650}.map-legend{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:10px;flex-wrap:wrap}.legend-dot{width:7px;height:7px;border-radius:2px;background:var(--teal)}.legend-hatch{width:14px;height:6px;background:repeating-linear-gradient(120deg,#b99d73 0 2px,#fff3df 2px 5px);margin-left:8px}.coverage-caption{font-size:11px;color:var(--muted);margin-top:11px}.failed-note{display:block;font-size:10px;color:var(--amber);margin-top:4px}.next-step{display:flex;align-items:center;gap:16px;border-top:1px solid var(--line);margin-top:26px;padding-top:22px}.next-icon{color:var(--teal);display:flex}.next-step .eyebrow{margin-bottom:3px}.next-step p:last-child{font-size:13px}.next-step>a{margin-left:auto;font-size:12px;white-space:nowrap;display:flex;align-items:center;min-height:44px}.view-intro,.verification-note{color:var(--muted);font-size:14px;margin:16px 0 24px}.warning{padding:18px 22px;margin:0 0 22px;border:1px solid #e3bf88;background:var(--amber-soft);border-radius:10px}.warning p{margin-top:8px}.warning h2{font-size:18px}
details{background:var(--paper);border:1px solid var(--line);border-radius:9px;margin:12px 0}summary{cursor:pointer;padding:16px;font-size:14px;font-weight:600;min-height:48px}summary:hover{background:#f1f7f7}.category>summary{display:flex;gap:12px;align-items:center}.category>summary:before{content:'+';font-size:18px;font-weight:400}.category[open]>summary:before{content:'−'}.category-count{margin-left:auto;white-space:nowrap;font-size:12px;color:var(--muted)}.detail-body{padding:8px 20px 20px}.detail-body>p,.detail-body>h3{margin:12px 0}.detail-body li{font-size:14px;margin:6px 0}.detail-body ul{padding-left:20px}.detail-body p{font-size:14px}.detail-body details>ul,.detail-body details>pre{margin:12px 20px 20px}.tier{font-size:10px;border-radius:4px;padding:4px 7px;background:var(--teal-soft);color:var(--teal);white-space:nowrap}.tier.review,.tier.strong{background:var(--amber-soft);color:var(--amber)}pre{background:#f1f4f4;padding:16px;font-size:12px;white-space:pre-wrap}img{max-width:100%;height:auto}code,a,li,pre{overflow-wrap:anywhere}footer{display:flex;align-items:center;gap:9px;font-size:11px;line-height:1.4;color:var(--muted);margin-top:30px;padding-top:20px;border-top:1px solid var(--line)}footer svg{width:16px;height:16px}.skip-link{position:absolute;left:12px;top:-70px;padding:12px;background:var(--paper);z-index:3}.skip-link:focus{top:8px}a:focus-visible,summary:focus-visible{outline:3px solid #387b89;outline-offset:4px}.label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:650;color:var(--muted)}
@media(min-width:1500px){main{max-width:1320px}.outcome-grid{padding:36px}.outcome h2{font-size:39px}.coverage-tile{padding:16px}.tile-top{font-size:10px}.coverage-tile h3{font-size:13px}}
@media(max-width:1000px){main{padding:0 24px 24px}.outcome-grid{grid-template-columns:1fr 1fr;padding:24px;gap:20px}.outcome h2{font-size:29px}.run-path{padding-left:20px}.coverage-map{grid-template-columns:repeat(3,1fr)}.evidence-card{padding:16px}.card-tag{font-size:9px}.card-top{gap:4px}.section-heading h2{font-size:21px}}
@media(max-width:650px){main{padding:0 16px 24px}.brand-bar{height:58px}.brand{font-size:10px;gap:6px}.brand>span{font-size:10px;padding-left:7px}.brand svg{width:20px}.private-label{font-size:10px}header{padding:24px 0 20px}h1{font-size:25px}.header-note{display:none}nav{gap:21px;margin-bottom:20px}nav a{font-size:12px}.outcome-grid{grid-template-columns:1fr;padding:22px}.outcome h2{font-size:31px}.outcome-copy{font-size:14px}.run-path{border-left:0;border-top:1px solid var(--line);padding:22px 0 0}.evidence-cards{grid-template-columns:1fr}.evidence-card{display:grid;grid-template-columns:64px 1fr;column-gap:14px;padding:18px}.card-top{grid-column:1/-1;margin-bottom:10px}.card-metric{grid-column:1;grid-row:2/4;font-size:38px}.evidence-card h3{grid-column:2;font-size:17px;max-width:none}.evidence-card p{grid-column:2;margin-top:6px;max-width:none}.card-action{grid-column:1/-1}.evidence-preview{grid-column:1/-1}.coverage-map{grid-template-columns:repeat(2,minmax(0,1fr))}.coverage-tile{padding:15px}.tile-top{font-size:10px}.coverage-tile h3{font-size:13px}.section-heading{align-items:start;gap:12px}.section-heading>a{max-width:112px;font-size:11px}.map-legend{max-width:118px;line-height:1.8}.legend-hatch{margin-left:0}.next-step{align-items:start;flex-wrap:wrap}.next-step>div{flex:1}.next-step>a{margin-left:40px}.category>summary{flex-wrap:wrap}.category>summary>svg{display:none}.category-count{margin-left:0}.detail-body{padding:8px 14px 16px}}
@media(prefers-reduced-motion:no-preference){a,summary{transition:background-color .15s,border-color .15s}}
@media print{main{max-width:none;padding:0}body{background:white}nav,.primary-link,.card-action,.section-heading>a,.next-step>a{display:none}.view[hidden]{display:none!important}.outcome-grid,.evidence-card,.coverage-map{break-inside:avoid}.outcome-grid{padding:20px}.brand-bar{height:48px}header{padding:18px 0}.section-heading{margin-top:18px}footer{font-size:10px}}
"""

# No external dependencies; fragments open the correct view and its evidence disclosures.
SCRIPT = """
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
