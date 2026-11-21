# Prototype milestone status

The public repository is [Abelo9996/integrity-agent](https://github.com/Abelo9996/integrity-agent).
M0–M5 have separate implementation commits. Hosted CI passed on Python 3.11 and 3.12
for commit `d9b50b6`; see [the verified run](https://github.com/Abelo9996/integrity-agent/actions/runs/44887318957).
The implementation, synthetic pilot and bounded M6 private run are available. The full
prototype definition of done has not been met; broader coverage and detector validation remain.

| Milestone | Local implementation and verification | Remaining work |
| --- | --- | --- |
| M0 | uv package, Apache-2.0, README, contributing/responsible-use docs, environment template, ignores, passing hosted CI and history hygiene checker | Complete |
| M1 | Candidate confirmation, OpenAlex pagination, source adapters, provenance manifests, SQLite/content cache; mocked transport/provenance tests and live PMC S3 collection | Full-author acquisition with key, broader source edge-case coverage |
| M2 | Hash variants, SIFT/RANSAC, local differences, copy-move, panel/caption provenance, overlays, procedural metrics | Paired PMC pilot complete; improve standalone copy-move and independently adjudicate harder negatives |
| M3 | GRIM and conservative GRIMMER lattice/parity, multi-item averages, seeded baseline Monte Carlo | Broader real-table validation and richer automatic extraction |
| M4 | Repeated row sequences, explicit distribution assumptions, XLSX internals/metadata | Real supplement coverage and domain-specific calibration |
| M5 | DOI update history, RW CSV, registry/field context, text reuse, provider interface, verified reports | Live provider and registry/baseline integration checks; richer benign-context interpretation |
| M6 | Confirmed profiles, bounded private acquisition, live ORCID CLI, verified HTML/JSON and illustrative evidence review; all individual outputs ignored | Independent expert adjudication, broader source coverage and detector refinement |

Latest procedural benchmark: 20/20 category 1, 100/100 category 2 and 40/40 category 3
manipulations detected and classified correctly; per-category precision/recall 100% at this
benchmark mixture. Copy-move recovered 20/20 clones. False positives: 0/100 unrelated pairs
and 0/100 unmodified images. The pair-level 95% upper false-positive bound is 3.62%.
This narrowly generated texture family does not establish biomedical performance.

The optional LLM is intentionally constrained to existing finding IDs and review questions;
report statements come from deterministic tool results. A verifier checks statement/tier,
artifact and work associations, and input file SHA-256 before claims reach reports. No
individual run output is saved in source files; private outputs stay in ignored folders.

Verification: all 60 tests pass locally on Python 3.11 and in hosted CI on Python 3.11
and 3.12. Ruff lint/format and light mypy checks pass. Tests prohibit real HTTP calls.
PyMuPDF emits upstream SWIG deprecation warnings during its test. The demo
evidence image was visually inspected. A source/config/docs credential-pattern scan
found no matches; full history hygiene checks passed before publication and in hosted CI.

The CC BY PMC pilot used 11 figures and 35 visually reviewed cross-article negative pairs.
Paired category-2/3 detection recall was 100%; classification precision was 100% for
category 2 and 95.65% for category 3. Standalone copy-move recovered 9/11 clones and
flagged 4/11 unmodified figures. These were not independently human-adjudicated.
Source images, manifests and person-specific candidate metadata are kept in ignored
runtime folders; only benchmark source citations and aggregate synthetic-manipulation
metrics are included in the repository.
