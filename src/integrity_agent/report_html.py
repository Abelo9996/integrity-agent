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


def render_report(report: dict) -> str:
    brief = report["reading_summary"]
    summary = report["summary"]
    author = report["author"]
    works = {w["id"]: w for w in report["works"]}
    artifacts = {a["artifact_id"]: a for a in report["artifacts"]}
    findings = {f["id"]: f for f in report["findings"]}
    rejected = report["verification"]["rejected"]
    counts = brief["counts_by_tier"]
    priority_count = counts["strong"] + counts["review"]
    total = len(works)
    parts = [
        '<header><p class="eyebrow">Private evidence review</p>',
        f"<h1>{esc(author['name'])}</h1>",
        '<p class="lede">A screening summary for human review.</p></header>',
        '<nav aria-label="Report sections"><a href="#summary">Summary</a>'
        '<a href="#coverage">What was checked</a><a href="#results">Results &amp; evidence</a>'
        '<a href="#papers">Work records</a></nav>',
    ]
    if rejected:
        reasons = Counter(item["reason"] for item in rejected)
        parts.append(
            f'<aside class="warning"><h2>Verification gaps</h2><p>{len(rejected)} claims were excluded before summary counts were calculated. '
            "Review these errors before interpreting this report.</p><ul>"
            + "".join(f"<li>{esc(reason)}: {count}</li>" for reason, count in reasons.items())
            + '</ul><a href="verifier-log.json">View rejected claim IDs and reasons</a></aside>'
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
    profile = report["review"].get("image_profile", "not recorded")
    if profile == "experimental-compression":
        parts.append(
            '<aside class="warning"><h2>Experimental image search</h2><p>This profile reduced signals in constructed negatives '
            "but missed more small smooth copies in regression tests. Its sensitivity is not established.</p></aside>"
        )
    parts.extend(
        [
            '<section><div id="summary" class="takeaway">',
            '<p class="eyebrow">What this run can tell you</p>',
            f"<h2>{esc(brief['headline'])}</h2>",
            "<p>Missing checks leave questions unanswered. No findings, or only informational results, "
            "do not establish that the underlying research is reliable.</p></div>",
            '<div class="metrics">',
            f"<div><strong>{total}</strong><span>work records in scope</span></div>",
            f"<div><strong>{priority_count}</strong><span>review / strong signals</span></div>",
            f"<div><strong>{counts['info']}</strong><span>informational results</span></div></div>",
            f'<p class="muted">{esc(brief["counting_note"])}</p>',
            '<h2>Read this first</h2><ul class="read-first">',
        ]
    )
    if priority_count:
        parts.append(
            f"<li><strong>Review the evidence:</strong> {counts['strong']} strong and {counts['review']} review-tier results "
            f"across {len(brief['priority_work_ids'])} work records. These are automated signals, not confirmed issues. "
            '<a href="#results">Inspect the results below.</a></li>'
        )
    else:
        parts.append(
            "<li><strong>No review- or strong-tier signals were reported.</strong> This is limited to the checks that actually ran.</li>"
        )
    for row in brief["categories"]:
        work_count = len(row["work_ids"])
        scope = (
            ""
            if row["kind"] == "output-context"
            else f" linked to {work_count} work {'record' if work_count == 1 else 'records'}"
        )
        parts.append(
            f'<li><a href="#{row["id"]}"><strong>{esc(row["label"])}</strong></a>: '
            f"{row['result_count']} {esc(TIERS[row['tier']].lower())} results{scope}. {esc(row['explanation'])}"
        )
        for status, work_ids in row.get("status_work_ids", {}).items():
            noun = "record" if len(work_ids) == 1 else "records"
            parts.append(
                f" <strong>{esc(status.replace('-', ' ').capitalize())} metadata is linked to {len(work_ids)} work {noun}.</strong>"
            )
        notice_count = len(row.get("notice_title_finding_ids", []))
        if notice_count:
            parts.append(
                f" <strong>{notice_count} of {row['result_count']} text matches involve only records with notice-style titles.</strong> "
                "Shared notice wording may explain these matches; confirm the document context in the sources."
            )
        parts.append("</li>")
    if not brief["categories"]:
        parts.append(
            "<li>No accepted detector results are available. Check coverage and any verification errors before interpreting this absence.</li>"
        )
    if brief["missing_core_checks"]:
        parts.append(
            f"<li><strong>Still unassessed:</strong> {esc(', '.join(brief['missing_core_checks']))}. "
            "Obtain eligible source material and check the required assumptions before rerunning these checks.</li>"
        )
    parts.extend(
        [
            '</ul><p class="muted">“Verified” means result references and evidence-file hashes passed the checks. '
            "It does not mean an expert confirmed the interpretation.</p></section>",
            '<section><h2 id="coverage">What was actually checked</h2>',
            "<p>A record is counted when at least one check in that category completed. This does not mean every check ran or all content was examined.</p>",
            '<div class="table-wrap"><table><thead><tr><th>Check</th><th>Records checked</th><th>Coverage</th></tr></thead><tbody>',
        ]
    )
    for row in brief["detector_coverage"]:
        status = {
            "some_checks_ran": "Some checks ran",
            "not_assessed": "Not assessed",
            "failed": "Checks failed",
        }[row["status"]]
        failed = len(row["work_ids_with_failed_check"])
        if failed and row["status"] != "failed":
            status += f"; {failed} record(s) also had failed checks"
        parts.append(
            f'<tr><th scope="row">{esc(row["label"])}</th><td>{row["works_with_completed_check"]} / {total}</td>'
            f"<td>{esc(status)}</td></tr>"
        )
    parts.append(
        '</tbody></table></div><details><summary>Coverage by individual check</summary><div class="table-wrap"><table>'
        "<thead><tr><th>Check</th><th>Completed</th><th>Failed</th></tr></thead><tbody>"
    )
    subchecks = sorted({(c["detector"], c["check"]) for c in report["detector_coverage"]})
    for detector, check in subchecks:
        events = [
            c
            for c in report["detector_coverage"]
            if (c["detector"], c["check"]) == (detector, check) and c["work_id"] in works
        ]
        ran = len({c["work_id"] for c in events if c["status"] == "ran"})
        failed = len({c["work_id"] for c in events if c["status"] == "failed"})
        parts.append(
            f'<tr><th scope="row">{esc(detector)} · {esc(check)}</th><td>{ran} / {total}</td><td>{failed} / {total}</td></tr>'
        )
    parts.append(
        '</tbody></table></div></details></section><section><h2 id="results">Results &amp; evidence</h2>'
        "<p>Open a category, then a result to inspect the exact detector statement, sources and limitations. "
        "Strong = higher detector tier; review = inspect the evidence; information = context. All require human interpretation.</p>"
    )
    for row in brief["categories"]:
        ids = set(row["finding_ids"])
        parts.append(
            f'<details class="category" id="{row["id"]}"><summary>{esc(row["label"])} '
            f'<span class="tier {row["tier"]}">{TIERS[row["tier"]]}</span> · {row["result_count"]} results</summary>'
            f'<div class="detail-body"><p>{esc(row["explanation"])}</p>'
        )
        for group in report["review_groups"]:
            if group["representative_id"] in ids:
                parts.append(_finding(group, findings, works, artifacts))
        parts.append("</div></details>")
    parts.append(
        '</section><details id="papers"><summary>Browse all '
        f'{total} work records and their coverage</summary><div class="detail-body">'
    )
    for w in sorted(
        works.values(),
        key=lambda w: (
            min(
                (TIER_ORDER[f["tier"]] for f in findings.values() if w["id"] in f["work_ids"]),
                default=3,
            ),
            -(w["year"] or 0),
            w["title"],
        ),
    ):
        fs = [f for f in findings.values() if w["id"] in f["work_ids"]]
        parts.append(
            f'<details><summary>{esc(w["title"])} · {len(fs)} result(s)</summary><div class="detail-body">'
            f"<p>{esc(w['year'] or 'Year unavailable')} · {esc(w['venue'])}</p>"
        )
        if fs:
            parts.append(
                "<ul>"
                + "".join(
                    f'<li><a href="#{finding_anchor(f["id"])}">{esc(TIERS[f["tier"]])}: {esc(f["statement"])}</a></li>'
                    for f in fs
                )
                + "</ul>"
            )
        else:
            parts.append(
                "<p>No accepted results for this record; see the coverage limits below.</p>"
            )
        parts.append("<details><summary>Individual check status and reasons</summary><ul>")
        for c in report["detector_coverage"]:
            if c["work_id"] == w["id"]:
                parts.append(
                    f"<li><strong>{esc(c['detector'])} / {esc(c['check'])}: {esc(c['status'])}</strong> "
                    f"({c['input_count']} inputs). {esc(c['detail'])}</li>"
                )
        parts.append("</ul></details></div></details>")
    parts.append(
        '</div></details><details id="technical"><summary>Collection log and technical details</summary><div class="detail-body">'
        f"<p>{summary['works_attempted']} works attempted; {summary['artifacts_collected']} artifacts collected. "
        f"Image search profile: {esc(profile)}.</p>"
    )
    attempts = brief["collection_attempts"]
    parts.append(
        f"<p>Collection log: {attempts.get('ok', 0)} successful, {attempts.get('skipped', 0)} skipped and "
        f"{attempts.get('failed', 0)} failed source attempts. These are not unique-paper counts.</p>"
        "<details><summary>Source log grouped by identical status and reason</summary><ul>"
    )
    logs = Counter((c["source"], c["status"], c["detail"]) for c in report["coverage"])
    parts.extend(
        f"<li>{count} × {esc(source)} · {esc(status)}: {esc(detail)}</li>"
        for (source, status, detail), count in sorted(logs.items())
    )
    parts.append(
        '</ul></details><p><a href="report.json">Complete JSON: findings, artifacts and per-record logs</a> · '
        '<a href="verifier-log.json">Verification log</a></p></div></details>'
        f"<footer>{FOOTER}</footer>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
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
:root{color-scheme:light;--ink:#192c36;--muted:#50616b;--border:#d8e0e4;--accent:#205d70}
*{box-sizing:border-box}body{margin:0;background:#f4f7f8;color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:1020px;margin:auto;padding:36px 24px 48px}h1,h2{line-height:1.2;letter-spacing:-.025em}
h1{font-size:2.35rem;margin:6px 0}h2{font-size:1.4rem;margin:0 0 14px}p{margin:10px 0 16px}
.eyebrow,.label{font-size:.75rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.lede{font-size:1.08rem;color:var(--muted)}nav{display:flex;gap:20px;flex-wrap:wrap;margin:24px 0}
a{color:var(--accent);text-underline-offset:3px}a:hover{text-decoration-thickness:2px}
section{background:white;border:1px solid var(--border);border-radius:12px;padding:24px;margin:20px 0}
.takeaway{padding:20px 22px;background:#f3f6f8;border-left:4px solid #688595;border-radius:4px;margin-bottom:20px}
.takeaway p:last-child{margin-bottom:0}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.metrics>div{padding:12px 0}.metrics strong{display:block;font-size:2rem;line-height:1.2;font-weight:650}
.metrics span{display:block;font-size:.88rem;color:var(--muted);margin-top:6px}.muted{color:var(--muted);font-size:.9rem}
.read-first{padding-left:22px}.read-first li{margin:12px 0}.warning{padding:22px;background:#fff5e4;border:1px solid #d6b783;border-radius:8px;margin:16px 0}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--border);vertical-align:top}
thead th{font-size:.77rem;text-transform:uppercase;color:var(--muted);letter-spacing:.04em}tbody th{font-weight:550}
details{border:1px solid var(--border);border-radius:8px;margin:12px 0;background:white}summary{cursor:pointer;padding:14px 16px;font-weight:600}
summary:hover{background:#f3f7f9}summary:focus-visible,a:focus-visible{outline:3px solid #39768d;outline-offset:3px}
.detail-body{padding:0 18px 16px}details>ul,details>pre{margin:0 18px 18px}.tier{display:inline-block;font-size:.75rem;padding:2px 9px;border-radius:20px;background:#eaf0f3;color:#304b5c;margin:0 5px}
.tier.review{background:#fff0d5;color:#6c470d}.tier.strong{background:#f8e2d8;color:#783c25}
img{max-width:100%;height:auto}pre{font-size:.8rem;background:#f4f6f8;padding:14px}pre,code,a,li{overflow-wrap:anywhere}pre{white-space:pre-wrap}
footer{border-top:1px solid var(--border);padding-top:22px;margin-top:28px;color:var(--muted);font-size:.9rem}
@media(max-width:600px){main{padding:22px 14px}h1{font-size:1.85rem}section{padding:18px}.metrics{gap:10px}.metrics strong{font-size:1.7rem}.metrics span{font-size:.8rem}nav{gap:14px}}
@media print{body{background:white}main{max-width:none;padding:0}nav,#technical{display:none}section,.takeaway{break-inside:avoid}a{color:inherit}}
"""

# No network, storage or model calls. Hash links reveal their collapsed ancestors.
SCRIPT = """
function revealHash(){
  const id=decodeURIComponent(location.hash.slice(1));
  const target=document.getElementById(id);
  if(!target)return;
  let node=target;
  while(node){if(node.tagName==='DETAILS')node.open=true;node=node.parentElement;}
  target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange',revealHash);
document.addEventListener('DOMContentLoaded',revealHash);
document.addEventListener('click',event=>{
  const link=event.target.closest('a[href^="#"]');
  if(link && link.hash===location.hash)revealHash();
});
"""
