# Evaluation protocol

The offline procedural smoke benchmark uses 20 held-out seeds (1000–1019), eight
manipulations per seed, 100 independently generated unrelated pairs, and 100 unmodified
self-images. Seed 40 is a development regression fixture, separate from that benchmark.
Run `uv run integrity-agent evaluate-images --seeds 20`.

The JSON includes both detection recall for injected manipulation categories and a separate
category classification confusion matrix with per-category precision/recall. Detecting shared
content in an edited image is not the same as correctly classifying the edit. Observed zero
false positives never establishes zero underlying false-positive probability. Precision depends
on the chosen positive/negative mixture; population positive predictive value is unknown.

## CC BY PMC pilot benchmark — 2026-11-21

```sh
# Contact email must be configured. Supply explicitly chosen source article PMCIDs.
uv run python scripts/prepare_pmc_evaluation.py PMC_SOURCE_ID
# Inspect corpus.json and original images; label visually reviewed unrelated pairs.
uv run python scripts/evaluate_pmc_corpus.py data/pmc-evaluation/corpus.json
```

The preparation script uses the current PMC S3 metadata, accepts CC BY only (not NC/ND/SA),
and records source URL, PMCID, SHA-256, license and original citation. Original downloads stay
under `data/`. Check the article's figure-specific credits for third-party exceptions before
redistribution. Do not add images to Git without that check and an attribution document.
The evaluation script explicitly standardizes images to central square crops at 320 pixels.
This is a starting benchmark, not native-resolution clinical validation. Include microscopy,
blots and charts, and retain hard negatives. Pre-register the corpus before tuning thresholds.

A corpus file has `figures` entries produced by the preparation script and
`confirmed_negative_pairs: [["artifact-id-1", "artifact-id-2"]]`. Different file names alone
are not sufficient negative labels. The evaluation refuses an empty negative set.

## Private sanity-check protocol (pending)

1. User selects one official public finding and several controls matched by field, career
   stage and approximate output. Preserve the official notice URL locally in `data/`.
2. Resolve each author and confirm the exact candidate before acquisition. Do not infer
   identity from a name alone. Confirm known paper identifiers against the official notice.
3. Record coverage denominators: indexed papers, acquired full text, acquired images and
   documented issues that are actually observable in the acquired artifacts.
4. Run the same frozen thresholds on the case and controls. Review all strong matches with
   original captions, versions, citations, corrections and common-experiment context.
5. Record recovered documented issues, missed accessible issues and control review burden.
   Controls are not guaranteed free of anomalies; do not call them verified negatives.
6. Share results privately with the requester. Keep all person-specific records and outputs
   under ignored local folders. Never include subject names or reports in public docs/history.

The CC BY PMC pilot has run; the author-level private sanity check remains pending.

### Pilot results

Sources: 11 CC BY figures from PMC10009416, PMC10014308 and PMC10669708; exact URLs,
content hashes and citations are in [source provenance](PMC_EVALUATION_SOURCES.json).
Downloaded images remain under ignored data/. This is a small convenience sample;
it includes multi-panel microscopy, plots, a table image and a graphical abstract.

| Injected category | Detected / total | Detection recall | Classification precision | Classification recall |
| --- | --- | --- | --- | --- |
| 1 | 11 / 11 | 100% | 100% | 100% |
| 2 | 55 / 55 | 100% | 100% | 98.18% |
| 3 | 22 / 22 | 100% | 95.65% | 100% |

One transformed image was classified as having localized differences (category 3).
There were 0 matches across 35 visually reviewed cross-article negative pairs.
These labels were reviewed by the assistant and have **not** been independently
adjudicated by a human. A descriptive binomial 95% upper bound is about 10%; pairs
share source images, so independence is not established and this is not a population bound.

Standalone copy-move detected 9/11 injected clones (81.82%), below 90%. It also
raised signals on 4/11 unmodified source figures; these are unadjudicated review signals,
not verified errors or evidence of misconduct, and demonstrate substantial review burden. All 22 category-3
pairs above were detectable when the original source image was available. These are
separate capabilities; do not substitute paired recall for standalone copy-move sensitivity.
The pilot used the thresholds already fixed before these downloads and made no detector
changes in response to pilot performance. More figure types, crops, arbitrary rotations,
low-texture blots, compression, and independently adjudicated negatives remain necessary.
