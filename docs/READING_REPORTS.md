# Reading a report

Open `report.html` for the file results or `summary.svg` for the one-page overview.
The top section shows the exact input files cited by review or strong detector findings,
with overlays when available. A flagged embedded image counts as one input file. The
PDF that supplied it is identified in the checked-source list. That list comes from
completed runtime checks and shows which local files can be opened.

Each publication action has the paper DOI, its notice DOI when available, and check
coverage. Multiple metadata sources for the same action and notice DOI appear as one
link in this view. The evidence library retains all accepted source records. A known
publication action may have no image or data checks in the current run.

Open the paper-by-paper matrix for per-paper details.
The paper queue opens to the most relevant group. Signals take priority, followed by
publication actions, checked research records, records with no completed research-data
checks, and documents whose titles indicate a notice. Each record appears once in the
queue. The top counts can overlap because a record with a notice can also have been checked.
Strong signals and records with completed image or data checks sort first within their group.

Open a paper to see its linked evidence and DOI. The six symbols on each row cover images,
summary statistics, trial baselines, raw data, registry comparisons and text. A dot means
at least one check ran. A half circle indicates both completed and failed checks in the same
category. An exclamation mark opens the corresponding detector evidence. The dash indicates
that the check did not run. Open check details for the ledger and missing inputs. Publication
status records appear through the separate action links. The original HTML report's evidence
library and coverage and sources views remain accessible.

PDF image checks use embedded raster images. Vector plots and scanned pages can escape
analysis. Files can contain adjacent articles. Compare the evidence to the exact figure and
paper before drawing conclusions. Notice-titled works are excluded from new research text
comparisons because standard notice language can create spurious matches. The title cue can
miss atypical notices. Text similarities in research papers remain informational findings.

Schema 1.6 adds `file_review` to JSON, with exact flagged input IDs, supporting finding IDs,
and checked source groups. It retains `paper_review` and the runtime ledger. The detailed `reading_summary`, original detector statements, evidence IDs and
coverage remain in JSON. A verification warning indicates any excluded claims. “Verified”
means source and evidence references and hashes passed the report's integrity checks.

Keep reports private. **Anomalies are not proof of misconduct. Findings require expert
human review.**
