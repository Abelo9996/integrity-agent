# Prototype scope and limitations

This tool works best on biomedical papers with open full text. It cannot detect problems
that leave no trace in public artifacts, and it does not establish intent. Its screening
patterns reflect published cases involving people who were caught: this is selection
bias, not a representative training population. The implementation is deterministic;
it does not contain a trained misconduct classifier.

## Coverage

- Author confirmation is mandatory. OpenAlex assignments and ORCID records can still be
  wrong. ORCID is used as an exact identifier, never as a name-similarity shortcut.
- Full OpenAlex cursor pagination needs a key. Failure aborts instead of silently returning
  a partial works list. `--max-works` deliberately limits analysis and records the gap.
- The PMC S3 adapter has collected three source articles successfully; other source adapters
  primarily have synthetic contract tests, and live credentials and
  institutional TDM entitlements have not been validated in this staging build.
- Downloads are bounded at 100 MB per response; archive expansion is bounded at 200 MB and
  2,000 members. Only regular archive entries are read. Nested formats, encrypted files,
  unsupported image formats, complex publisher XML and some relative asset URLs may be missed.
- Only literal links in data availability statements lead to data repositories. No name
  search or arbitrary repository crawling is performed. GEO accepts accession links.
- PMC uses the 2026 versioned S3 layout. Europe PMC supplements may be unavailable independently
  of full text. arXiv licenses vary; downloaded sources are never automatically redistributable.
- The cache is content addressed in SQLite plus blob files; mutable API metadata expires
  after 24 hours, PMC media after 30 days. Cache hits are checked against their content hash.
- Robots rules are enforced for web downloads. Official API and S3 API requests follow
  documented API access terms; HTTP 401/403, CAPTCHAs and paywalls are not bypassed.
- A report with no flags may have very little accessible evidence. Read collection coverage.

## Detector interpretation

| Detector | Implemented | Important limit |
| --- | --- | --- |
| D1 | p/d/w hashes over rotations/flips, SIFT ratio matching and RANSAC, localized aligned residuals, translation copy-move, overlays | Texture-poor blots, charts, tiny crops, blending and natural repeated structure remain difficult; pair search is quadratic. |
| D2 | Integer mean lattice and necessary SD moment/parity constraints; exact repeated mean/SD pairs | GRIMMER passing is not proof of an attainable bounded sample; multi-item averages use participant-level totals, not n×items independent observations. |
| D3 | Seeded normal-group-mean Monte Carlo, both tails, Bonferroni within table | Carlisle-style approximation, not validated clinical software; rounding, correlation, stratification and model assumptions affect calibration. |
| D4 | Repeated row blocks; optional low-skew, cap and terminal-digit checks; XLSX fonts, calcChain and metadata | Formatting and calculation order are ordinary process traces; information tier by default. Distribution assumptions must be supplied. |
| D5 | Exact DOI publication updates, RW CSV join, current registry differences, sampled OpenAlex topic baseline | Baseline is not career matched; registry changes require historical expert review and verified paper-field input. |
| D6 | Eight-token overlap, results/legends weighted above other sections | Exact self-reuse only; paraphrases, attribution and common methods require human judgment. |

Bik-style categories are operational descriptions. Category 1 is exact visual duplication;
category 2 is transformed matching content; category 3 is within-image copy-move or localized
aligned differences. Compression, annotations and resampling can create local differences.
No category identifies intent. Matches between sources or versions of the same work are
information tier; within-image duplication still warrants separate examination.

## Extraction and LLM boundary

JATS tables are exported directly. Automatic typed statistics require separate, unambiguous
mean/SD/n columns. Integer-scale and multi-item assumptions are never inferred automatically.
Use reviewer-supplied `--review-input` for those assumptions, baselines, registry fields and
raw-data distribution expectations. Numerical values must occur in extracted source text.

With `--llm`, PDF rows use structured output and must include an exact source excerpt with
the numbers and labels. Rejected rows are logged. PDF model input is capped at 100,000
characters; embedded image extraction remains native and independent of model success.
Percentage-specific extraction and complex multi-level table layouts are not implemented.

The optional model prioritizes detector IDs and selects benign-review questions. It cannot
supply new report finding text, upgrade a tier, or assert that a benign explanation is proven.
The HTML/JSON renderer reconstructs claims from deterministic results. The verifier removes
unknown IDs, altered statements/tiers, mismatched artifact references and absent/tampered
source files. This structural verifier does not establish detector scientific validity.
Provider use sends excerpts/captions to the configured service; it is opt-in.

## Validation status

A small CC BY PMC pilot now accompanies the procedural benchmark; see EVALUATION.md.
Paired category-2/3 detection was 100%, while standalone clone recall was 81.82%.
Private official-case/matched-control validation remains outstanding pending an OpenAlex
key and exact author-profile confirmation. Do not describe this prototype as validated or complete.
