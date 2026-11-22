# Reading a report

Open `report.html` for the dashboard or `summary.svg` for the one-page visual summary.
The overview answers: **What did this run establish, what did it check, and what is next?**

The outcome describes the run, never the person:

- **Inconclusive · missing inputs:** no image, statistics or raw-data checks completed.
- **Evidence needs review:** accepted detector results reached review or strong tier.
- **Limited to the checks run:** some research-data checks ran without review-level signals.
- **No records in scope:** no publication records were included.

None of these outcomes establishes that the research is reliable. Rejected claims remain
excluded from all counts, and a verification warning stays visible when claims are rejected.

## The visual overview

The collection path shows publication records, document files and records with at least one
completed image/statistics/raw-data check. These use different units; it is not a conversion
rate. Publication records may include notices and versions. Document files are PDF, XML or
text artifacts, including downloads linked through metadata and files extracted from
archives. A downloaded document is not automatically original research content.

Up to three evidence cards appear in review priority order. Every category remains available
in the evidence library. Publication-notice cards count distinct linked work records; the
other cards count detector results. For example, two metadata sources for one synthetic
correction count as one work record on the card and two tool results in the library. A title
cue can identify notice-like records but cannot prove document type or explain a match.
Image cards show a preview of the verified detector evidence when available.

The six coverage tiles count distinct records with at least one completed check in each
category. Blue bars mean some checks ran, not that the research passed. Hatched bars and
“Not tested” labels distinguish missing checks from negative results. Counts are labeled
directly; color is not the only cue. Publication-status checks do not imply registry
comparisons ran, and an image self-check does not imply cross-paper matching ran.

## Evidence and coverage views

Each card opens its evidence category. Open a result for the unchanged detector statement,
source files, limitations, IDs and measurements. Equivalent image evidence appears once,
with every raw finding ID retained. Deep links reveal the appropriate view and disclosure.

Click a coverage tile for individual check counts and missing-input reasons. The coverage
and sources view also contains the work-record index, source log and complete JSON.
“Verified” means identifiers and source/evidence hashes passed deterministic checks;
it does not mean an expert confirmed a scientific interpretation.

The report works offline. With JavaScript disabled, all three views remain readable in
sequence, with evidence details collapsed. The standalone SVG has no scripts or network
dependencies; its cards link to the HTML evidence and its metadata retains summary IDs.

## Data contract

Schema 1.4 extends `reading_summary` with `outcome`, `collection` and `cards`. All result
aggregates are computed after both verifier stages and preserve finding/artifact IDs.
Coverage comes from the runtime ledger; document counts and title cues use linked artifact
and work metadata. No model creates or upgrades a finding. Reports and visual summaries
are presentations of existing evidence, not a new detector or independent validation study.

Keep reports private. **Anomalies are not proof of misconduct. Findings require expert
human review.**
