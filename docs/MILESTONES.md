# Prototype milestone status

Repository naming and publication are approved. M0–M5 are being committed separately
in an independent repository; the original unrelated workspace is not part of its history.
Hosted CI status will be recorded after the initial push.

| Milestone | Local implementation and verification | Remaining work |
| --- | --- | --- |
| M0 | uv package, Apache-2.0, README, contributing/responsible-use docs, environment template, ignores, CI and history hygiene checker | Run hosted CI after the initial push |
| M1 | Candidate confirmation, OpenAlex pagination, source adapters, provenance manifests, SQLite/content cache; mocked transport/provenance tests | Live API checks with contact email/key, source edge-case coverage |
| M2 | Hash variants, SIFT/RANSAC, local differences, copy-move, panel/caption provenance, overlays, procedural metrics | Paired PMC pilot complete; improve standalone copy-move and independently adjudicate harder negatives |
| M3 | GRIM and conservative GRIMMER lattice/parity, multi-item averages, seeded baseline Monte Carlo | Broader real-table validation and richer automatic extraction |
| M4 | Repeated row sequences, explicit distribution assumptions, XLSX internals/metadata | Real supplement coverage and domain-specific calibration |
| M5 | DOI update history, RW CSV, registry/field context, text reuse, provider interface, verified reports | Live provider and registry/baseline integration checks; richer benign-context interpretation |
| M6 | Private run protocol documented; all runtime directories ignored | Select and confirm official case and matched controls, acquire, run, review, share privately |

Latest procedural benchmark: 20/20 category 1, 100/100 category 2 and 40/40 category 3
manipulations detected and classified correctly; per-category precision/recall 100% at this
benchmark mixture. Copy-move recovered 20/20 clones. False positives: 0/100 unrelated pairs
and 0/100 unmodified images. The pair-level 95% upper false-positive bound is 3.62%.
This narrowly generated texture family does not establish biomedical performance.

The optional LLM is intentionally constrained to existing finding IDs and review questions;
report statements come from deterministic tool results. A verifier checks statement/tier,
artifact and work associations, and input file SHA-256 before claims reach reports. No
real-person run has been performed or saved in source files.

Local verification: 45 tests pass on Python 3.11; the original 43-test suite and both
new integration regressions pass on Python 3.12. Ruff lint/format and light mypy checks
pass. PyMuPDF emits upstream SWIG deprecation warnings during its test. The demo
evidence image was visually inspected. A source/config/docs credential-pattern scan
found no matches; full history hygiene checks run before publication and in hosted CI.

The CC BY PMC pilot used 11 figures and 35 visually reviewed cross-article negative pairs.
Paired category-2/3 detection recall was 100%; classification precision was 100% for
category 2 and 95.65% for category 3. Standalone copy-move recovered 9/11 clones and
flagged 4/11 unmodified figures. These were not independently human-adjudicated.
Source images, manifests and person-specific candidate metadata are kept in ignored
runtime folders; only benchmark source citations and aggregate synthetic-manipulation
metrics are included in the repository.
