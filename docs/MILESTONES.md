# Prototype milestone status

The public repository is [Abelo9996/integrity-agent](https://github.com/Abelo9996/integrity-agent).
M0–M5 have separate implementation commits. The
[CI workflow](https://github.com/Abelo9996/integrity-agent/actions/workflows/ci.yml)
checks Python 3.11 and 3.12; inspect the run associated with the revision you use.
The implementation, synthetic pilot and bounded M6 private run are available. The full
prototype definition of done has not been met; broader coverage and detector validation remain.

| Milestone | Local implementation and verification | Remaining work |
| --- | --- | --- |
| M0 | uv package, Apache-2.0, README, contributing/responsible-use docs, environment template, ignores, passing hosted CI and history hygiene checker | Complete |
| M1 | Candidate confirmation, complete OpenAlex pagination, source adapters, provenance/cache, independent PMC asset attempts and validated OA-location PDF fallback; offline contract tests and earlier live PMC S3 collection | Broader live coverage and full-corpus artifact acquisition |
| M2 | Hash variants, texture-supported SIFT/RANSAC, local differences, copy-move, small-region pixel/residual corroboration, original-figure coordinates, overlays, frozen procedural evaluation | Compression robustness, smooth-image sensitivity, licensed standalone clone localization and independently adjudicated negatives |
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

Verification includes 96 offline tests, Ruff lint/format and light mypy checks.
Tests prohibit real HTTP calls; CI runs the suite on Python 3.11 and 3.12.
PyMuPDF emits upstream SWIG deprecation warnings during its test. The demo
evidence image was visually inspected. A source/config/docs credential-pattern scan
found no matches; full history hygiene checks passed before publication and in hosted CI.

The latest follow-up freezes fixtures at `d650474` and the image detector at `31cf89b`.
Held-out procedural small-region localization is 76/80 without compression and 5/20
after JPEG, with 0/120 negative-test signals. The 11-figure PMC regression corpus gives
51/55 category-2 detection (down from 55/55), 22/22 category-3 detection and 0/35
unrelated-pair matches. Standalone localization is 8/11 for both versions; the old 9/11
any-signal count included an off-target result. Four of 11 unmodified figures still trigger
signals. See [complete counts and limitations](EVALUATION.md). These labels were not
independently human-adjudicated, and private reports were not rerun for this iteration.
Source images, manifests and person-specific candidate metadata are kept in ignored
runtime folders; only benchmark source citations and aggregate synthetic-manipulation
metrics are included in the repository.

The subsequent verifier update adds schema 1.1, unique finding/artifact/claim references,
creation-time evidence hashes and resolved-path confinement. Synthetic regressions reproduce
the previous duplicate-ID rendering error and missing-overlay acceptance, then verify that
claims are rejected. Private reports and image detector thresholds remain unchanged; see
[the verification contract and next priorities](EVIDENCE_VERIFICATION.md).

## Compression, execution coverage and review preparation follow-up

New fixtures were frozen at9a243ab and the experimental matcher at71afab0 before holdout.
It localized81/96newcases with0/64constructed-negative signals, but regression losses keep
it opt-in. Standard behavior is retained and replayed against the previous implementation.
Schema1.2 records actual subcheck coverage and groups equivalent verified image evidence;
all raw claims/IDs remain available. The local24-case licensed packet and incomplete-label
scorer are ready, with every human label pending. New native clone localization is0/6.
101offline tests pass, with lint, types and demo checks. The scientific definition of done
remains unmet; see [measured tradeoffs](COMPRESSION_ITERATION.md) and [review protocol](INDEPENDENT_REVIEW.md).
