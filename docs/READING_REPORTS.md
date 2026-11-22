# Reading a report

Open `report.html`. The first section explains what the run can establish, which checks
could not be assessed, and the results that need context. Read coverage before interpreting
a zero: no signal from missing inputs is not a negative result.

The three counters show work records in scope, review/strong-tier results, and informational
results. They are not a score or a count of confirmed problems. Work records can include
notices and different versions of a paper. Several sources can report the same notice.

Results are summarized by type and original detector tier. For example, two source records
for one synthetic correction count as two informational results linked to one work record;
the summary does not claim there were two independent corrections. Text overlap involving
records with notice-style titles is explicitly labeled as a title cue. Shared wording may
explain it; this does not prove the document type or establish a benign explanation.

The coverage table counts distinct work records with at least one completed check in each
category. This is not exhaustive coverage: publication-status checks do not imply registry
comparisons ran, and an image self-check does not imply cross-paper matching ran. Expand
individual checks or a work record to see missing inputs and failures. A work may have both
completed and failed checks. Source-attempt counts are separate from work counts.

Open a result category, then a result, to see the unchanged detector statement, evidence,
linked work records, limitations and source IDs. Repeated equivalent image evidence appears
once in this list with every underlying finding ID retained. The work-record index links to
these same results instead of repeating them. Deep links open the relevant evidence; the
report remains readable offline without JavaScript using its expandable sections.

“Verified” means identifier associations and evidence-file hashes passed the deterministic
checks. It does not mean a human confirmed a scientific interpretation. Rejected findings
are excluded from every summary count and shown in a prominent verification warning.

Schema 1.3 adds `reading_summary` to JSON while retaining all existing evidence and coverage
fields. Its result categories are computed only after both verifier stages, with explicit
finding, artifact and work IDs. Coverage comes from the runtime ledger; title cues come
from linked work metadata. No model writes or upgrades a summary finding. The HTML is a
view of these aggregates, not another detector or an independent validation study.

Keep reports private. **Anomalies are not proof of misconduct. Findings require expert
human review.**
