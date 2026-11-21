# Evaluation protocol

## Current image iteration

The detector now requires distributed texture around SIFT keypoints to reduce matches
supported only by ordinary typography, rules and hatching. A bounded, separate search
proposes dark components on light backgrounds and corroborates their pixels and fine
residuals. These small-region results are **review** tier, not strong. Both paths record
matched coordinates in normalized panels and original figure pixels. The content gate
is a heuristic, not an OCR model or a decision about what an image depicts.

The fixture generator was committed as `d650474`, then detector parameters were frozen
at `31cf89b` before evaluation. Development seeds were 20–23; evaluation seeds were
3000–3019. No private-case images or outcomes were used to tune this iteration.
The generator inserts a 64×30-pixel patch into a 720×480 figure; its visible band is smaller.
Recovery requires at least four correspondences inside **both** injected regions.
For legacy paired results, the evaluator captures the points actually drawn in the overlay;
it does not treat missing coordinate metadata as a detection failure or change match decisions.

```sh
uv run python scripts/evaluate_image_regions.py --output outputs/regions/metrics.json
# Optional historical comparison (local saved source stays ignored):
mkdir -p data/benchmark
git show d2faf5a:src/integrity_agent/detectors/images.py > data/benchmark/baseline_images.py
uv run python scripts/evaluate_image_regions.py --baseline data/benchmark/baseline_images.py --output outputs/regions/baseline.json
```

| Held-out procedural check | Previous detector | Current detector |
| --- | --- | --- |
| Small translated copy, localized | 0/20 | 19/20 |
| Small flipped copy, localized | 0/20 | 19/20 |
| Small brightness-adjusted copy, localized | 0/20 | 19/20 |
| Small copy between independent figures, localized | 0/20 | 19/20 |
| Small copy followed by JPEG quality 95, localized | 0/20 | 5/20 |
| Signals on independent-band / shared-layout negative tests | 76/120 (63.3%) | 0/120 (0%) |

That is **76/80 (95%) uncompressed localization**, but only **81/100 (81%) including JPEG**.
The negatives comprise 20 each of independent-band self-checks, independent figures with
shared annotations, table self/pair checks and plot self/pair checks. The fixtures share
templates and are not independent biomedical examples. Zero observed false positives does
not establish a zero population rate. These are measured stress-test rates, not clinical accuracy.

### Regression results and tradeoffs

The procedural texture benchmark still detects/classifies all 20 category-1, 100 category-2
and 40 category-3 pairs, localizes all 20 large clones, and produces 0/100 unrelated-pair
and 0/100 unmodified-self signals.

On the **same** 11-figure CC BY PMC pilot described below, paired detection is now
11/11 category 1, **51/55 category 2 (92.73%, previously 100%)**, and 22/22 category 3.
Category-2 classification recall is 48/55 (87.27%) with 100% precision; category-3
classification recall is 100% with 22/25 (88%) precision. The content gate can remove
valid support from smooth or diagrammatic experimental figures. This regression is retained
and disclosed; parameters were not retuned after observing the corpus results.

There remain 0/35 unrelated-pair matches and 4/11 unmodified-figure copy-move signals.
Current standalone any-signal recall is 8/11. A localization audit corrected the older
9/11 figure-level count: one old signal did not locate the injected clone. **Actual clone
localization is 8/11 (72.73%) for both versions**, so this iteration does not improve that
licensed-corpus result. Scripts now output localization separately from the legacy
`copy_move_recall` any-signal metric. Never substitute one for the other.

Machine-readable counts, confusion matrices and detector/fixture hashes are in
[D1_ITERATION_RESULTS.json](D1_ITERATION_RESULTS.json). The corpus is reused regression data;
the negative labels have not received independent expert review. The private author-level
reports were not rerun, and no improved private-case recovery or coverage is claimed.

Implementation references checked for this iteration:
[OpenCV template matching](https://docs.opencv.org/4.13.0/d4/dc6/tutorial_py_template_matching.html)
and [thresholding](https://docs.opencv.org/4.13.0/d7/d4d/tutorial_py_thresholding.html).
These document the image operations, not the scientific validity of the detector.

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

## Private sanity-check protocol

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

The CC BY PMC pilot and a bounded author-level private run have completed. Private review
was illustrative rather than exhaustive: expert adjudication of every strong finding remains
outstanding. Individual identities, artifacts, reports and outcome counts are not committed.
A figure-level flag does not establish recovery of a documented issue; the matched regions
must agree with the reference, and available versions may already incorporate corrections.

### Historical pilot results before the current iteration

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

Standalone copy-move raised a signal on 9/11 injected-clone images (81.82%), below 90%;
the subsequent localization audit above found that only eight located the clone. It also
raised signals on 4/11 unmodified source figures; these are unadjudicated review signals,
not verified errors or evidence of misconduct, and demonstrate substantial review burden. All 22 category-3
pairs above were detectable when the original source image was available. These are
separate capabilities; do not substitute paired recall for standalone copy-move sensitivity.
The pilot used the thresholds already fixed before these downloads and made no detector
changes in response to pilot performance. More figure types, crops, arbitrary rotations,
low-texture blots, compression, and independently adjudicated negatives remain necessary.
