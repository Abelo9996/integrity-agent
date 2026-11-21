# Compression and native-resolution experiment

The **standard profile remains the default**. `--experimental-compression` enables a
frozen alternative with improved scaling and fewer smooth-envelope signals in new
procedural fixtures, but substantial sensitivity regressions elsewhere. It is not a
validated replacement. The prototype's scientific definition of done remains unmet.

## Protocol and results

Fixtures were committed at `9a243ab` before detector changes. Development used seeds
60–62; held-out seeds 41000–41007 use different positions and larger canvases. Two
procedural families represent irregular lanes and Gaussian cell-like spots. Each has
native copies, JPEG quality 95/85/75, recompression, and 1.25× scaling. Negatives include
independent regions, independently noisy smooth twins, and shared annotations.
These families and transformations are correlated, not independent biomedical samples.

Experimental thresholds were frozen at `71afab0` before holdout execution. Later profile
selection preserves both algorithms; replay confirms identical positive/negative counts
for the experimental profile and the earlier standard implementation. No thresholds were
changed in response to holdout, regression or new licensed-source results. Development
localized 33/36 copies, with 0/24 negative signals. Baseline development localized 19/36,
with 15/24 negative signals.

| Untouched holdout, localized / total | Standard | Experimental |
| --- | ---: | ---: |
| Native | 15/16 | 15/16 |
| JPEG 95 | 16/16 | 16/16 |
| JPEG 85 | 16/16 | 12/16 |
| JPEG 75 | 15/16 | 9/16 |
| Recompressed | 13/16 | 15/16 |
| Scaled 1.25× | 0/16 | 14/16 |
| All positives | 75/96 (78.1%) | 81/96 (84.4%) |
| Signals on constructed negatives | 40/64 (62.5%) | 0/64 (0%) |

Experimental lanes localized 47/48; cell-like cases localized 34/48. In particular,
cell JPEG85 fell from 8/8 to 4/8 and JPEG75 from 7/8 to 1/8. These are measured negative
signal rates on constructed examples, not population false-positive probabilities.
A figure-level signal counts as localization only when at least four correspondences
fall inside **both** injected regions. No overall person score is calculated.

## Regression checks and release decision

| Previously exposed set | Standard / previous | Experimental |
| --- | ---: | ---: |
| Small bands, uncompressed localization | 76/80 | 48/80 |
| Small bands, JPEG95 localization | 5/20 | 0/20 |
| Small-band/layout negatives | 0/120 | 0/120 |
| Licensed paired category 2 detection | 51/55 | 51/55 |
| Licensed paired category 3 detection | 22/22 | 22/22 |
| Licensed standalone clone localization | 8/11 | 8/11 |
| Unmodified licensed self-image signals (unadjudicated) | 4/11 | 1/11 |
| Licensed cross-article pair signals | 0/35 | 0/35 |

The old 20-seed textured smoke benchmark remains 20/20 category1, 100/100 category2,
40/40 category3, 20/20 standalone localization, and zero signals on 100 unrelated pairs
and 100 self-negatives. Strong performance on that generator does not transfer to the
new native figures. The default is preserved because the experimental gate loses too
many small smooth copies. It is available for explicit comparison, not auto-selected.

The experimental component path retains native pixels up to a 2400-pixel side, tests
0.8/1/1.25 scales, and adds low-rank-envelope and compression-detail corroboration.
The SIFT path remains bounded at 900 pixels. Small-region findings are review tier;
shared scanner structure, labels, figure assembly and reused controls still need context.
Search remains bounded and quadratic over panels. No private author runs were repeated.

Operation references: [OpenCV template matching](https://docs.opencv.org/4.13.0/d4/dc6/tutorial_py_template_matching.html),
[filtering](https://docs.opencv.org/4.13.0/d4/d13/tutorial_py_filtering.html).
These describe operations, not forensic validity.

## Reproduce

```sh
uv run python scripts/evaluate_compression.py --development --output outputs/compression-development.json
uv run python scripts/evaluate_compression.py --output outputs/compression-heldout.json
uv run python scripts/evaluate_compression.py --standard --output outputs/standard-heldout.json
# Explicit experimental profile in a private author run:
uv run integrity-agent run --orcid <ORCID> --experimental-compression
```

Do not tune further on these now-exposed examples. New development/holdout families and
independent expert localization are required. Machine-readable aggregates and source/code
hashes are in [COMPRESSION_RESULTS.json](COMPRESSION_RESULTS.json).
