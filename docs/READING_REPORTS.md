# Reading a report

Open `report.html` to review individual papers or `summary.svg` for the one-page overview.
The first three counts show records with review signals, existing publication actions,
and completed image or data checks. A zero for review signals applies only to the checks
that completed. The coverage count gives the denominator. The publication-action card also
reports how many retraction-linked records received image or data checks.

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

Schema 1.5 adds `paper_review` to JSON. The queue consumes verified findings and the recorded
check ledger. The detailed `reading_summary`, original detector statements, evidence IDs and
coverage remain in JSON. A verification warning indicates any excluded claims. “Verified”
means source and evidence references and hashes passed the report's integrity checks.

Keep reports private. **Anomalies are not proof of misconduct. Findings require expert
human review.**
