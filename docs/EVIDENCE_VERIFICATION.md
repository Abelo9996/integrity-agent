# Evidence verification

Report schema **1.3** retains the reference and file checks introduced in schema 1.1.
This is an integrity check on the report pipeline, not scientific validation of detectors.

## Claim and identifier checks

`report.verify()` performs deterministic structural checks:

- A claim references exactly one finding. Duplicate finding IDs are rejected, including
  identical duplicates; a dictionary's last entry must never select which result is trusted.
- Repeated claims for one finding and ambiguous artifact IDs are rejected.
- Claim text, tier, artifact references and work/artifact associations match the detector.
- D1 image-reuse and copy-move findings include evidence files.
- Every declared evidence file has exactly one recorded SHA-256, and paths are canonical
  relative paths under `evidence/`.

These checks prevent conflicting findings with one ID from leaking an uncited statement
or an unverified strong tier into HTML, JSON or summary counts. Rejected claims are logged.
The HTML displays rejection counts and reasons before paper findings, with a link to the
verification log, so verification failure cannot look like an uneventful completed review.

## File checks

The pipeline writes detector overlay arrays to PNG, then records each file's SHA-256 in
`Finding.evidence_sha256`, keyed by its relative `evidence_files` path. The renderer checks
the source-artifact and evidence bytes before including a claim. Missing, unreadable or
changed files cause rejection. Resolved evidence paths must remain inside the report's
`evidence/` directory, including after symlink resolution. Traversal, absolute and encoded
escape paths are rejected. Structural verification alone does not check file bytes;
`write_report()` runs both stages.

Only accepted findings enter the concise `reading_summary` and its counts. Categories
retain all finding and artifact IDs; they do not infer independent issue counts or change
detector tiers. Coverage summaries use distinct work IDs from the runtime ledger. See
[reading reports](READING_REPORTS.md) for the presentation and counting rules.

Hashes are checked at report generation. They do not authenticate an entire report against
someone who can replace both its contents and recorded digests, and they do not establish
that a detector's interpretation is correct. A result may still have an ordinary explanation.

The implementation uses Python's [SHA-256 support](https://docs.python.org/3.11/library/hashlib.html)
and [resolved filesystem paths](https://docs.python.org/3.11/library/pathlib.html#pathlib.Path.resolve).

## Existing reports

Schema-1.0 reports remain historical outputs. New image claims without recorded evidence
digests are rejected; the renderer does not silently hash old overlays and declare them
verified. Regenerate evidence through the pipeline to produce a schema-1.1 report. Existing
private author reports are unchanged and were not rerun as part of this verifier update.

## Remaining priorities

1. Improve compression and smooth-image localization using new development data and an
   untouched test set; keep false-positive and localization measures separate.
2. Evaluate on new article/figure families, with independently reviewed positive and benign
   examples. More seeds from the same generator do not establish external validity.
3. Show eligibility and coverage per detector and paper, and group repeated evidence so
   multiple copies of a figure do not inflate the review workload.
4. Add a reproducibility manifest recording code revision, dependency versions and public
   detector settings, without secrets. Evaluate candidate retrieval before larger author runs;
   the current exhaustive pair search is quadratic.

## Schema 1.2: execution coverage and presentation groups

`detector_coverage` records work, detector, subcheck, artifact references, input count,
`ran`/`not_assessed`/`failed`, and a scope/reason. It is populated from runtime operations,
not the agent plan or the existence of an artifact. Subchecks have separate prerequisites;
for example, repeated means can be assessed while GRIM/GRIMMER remain ineligible.
`works_attempted` counts selected works. `works_analyzed` now counts works with at least
one recorded completed check, not comprehensive examination. Acquisition coverage remains
separate. A failure and successful checks can coexist for a paper. Input counts are specific
to the check (panels, pairs, rows or variables), not a comparable quality score.

`review_groups` is computed only after structural and file verification. Equivalent image
results require the same work-qualified source hashes, parameters, measurements (excluding
panel identifiers), overlay hashes, kind/tier and limitations. Different regions, encodings
or work associations remain separate. Every verified claim and raw finding remains in JSON;
HTML shows one representative overlay and all member finding IDs/source links. Grouping
never introduces an anomaly claim. Conflicting duplicate IDs are retained for rejection;
the pipeline coalesces only identical full detector outputs, never a last-wins ID mapping.

A `run-manifest.json` records Python/dependency versions, detector source hashes, input
hashes and image profile without environment variables or credentials. These hashes support
reproducibility; they are not signatures, semantic proof, or a calibrated detector evaluation.
