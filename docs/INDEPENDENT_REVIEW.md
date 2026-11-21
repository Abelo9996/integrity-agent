# Independent review preparation

A review packet generator, scorer and a local 24-case packet are prepared. **No independent
human review has been performed.** All 24 human labels remain pending. There is no estimated
human-adjudicated negative signal rate. The software cannot authenticate a reviewer's
expertise or independence.

The new source families are PMC10819415, PMC10151465 and PMC11875362, separate from the
previous licensed benchmark. They were chosen by article topic and open license, not an
author allegation or detector outcome. The first two source URLs per article were selected
before prediction: six native figures. They include plots, microscopy and multi-panel
experimental figures. Metadata identifies CC BY; the selected figure captions and article
permissions were checked for separate credit restrictions. Source citations, URLs, licenses
and hashes are in [INDEPENDENT_REVIEW_SOURCES.json](INDEPENDENT_REVIEW_SOURCES.json).
Original downloads and generated variants remain in ignored folders.

Each figure supplies an unmodified self-image, a flipped pair, an injected clone, and a
cross-article pair. Cross-article and unmodified examples are **unlabeled**, not presumed
negative. Clone source regions are selected by variance on a fixed grid before detection;
that does not guarantee biologically informative content. The packet uses native dimensions,
not central 320-pixel square crops. Detector search limits still apply.

Frozen experimental predictions detected all 6 flipped pairs. Standalone clone detection
raised 4 signals on 6 injected cases but localized **0/6** injected clones under the four-point,
two-region criterion. Off-target signals do not count as recovery. This exposes an important
native multi-panel limitation. These programmatic manipulation labels are separate from
human interpretation; they do not describe the integrity of the source papers or authors.

## Local workflow

```sh
uv run python scripts/prepare_pmc_evaluation.py PMC_SOURCE_1 PMC_SOURCE_2 --output data/new-review
# Inspect figure-specific credits before preparing views.
uv run python scripts/review_packet.py prepare outputs/new-review --corpus data/new-review/corpus.json
uv run python scripts/review_packet.py predict outputs/new-review --experimental-compression
uv run python scripts/review_packet.py score outputs/new-review
# After an independent reviewer returns a completed label file:
uv run python scripts/review_packet.py score outputs/new-review --labels outputs/reviewer-labels.json
```

Give reviewers only the `reviewer/` directory. Its index shows images and attribution,
with no detector predictions, overlay highlights, transformation names or injected truth.
The separate `coordinator/` directory retains frozen manifests, source/derived hashes,
truth, predictions and detector hashes. Preparation refuses an existing packet; prediction
refuses to overwrite an existing prediction set. Keep both private during adjudication.
No tool emails or uploads a packet.

Reviewers label `duplicated`, `distinct`, `uncertain` or `pending`, supply an identifier and
rationale for answered cases, and record region coordinates where applicable. Review
experimental regions separately from labels/axes, disclosed reuse and shared controls.
Seek a second independent reviewer and adjudicate disagreements before a validation claim.
A visual duplication label does not establish intent, responsibility or misconduct.

Scoring rejects missing/duplicate/unknown case IDs, changed manifests/images and answered
labels without a reviewer ID/rationale. Pending and uncertain rows are excluded from binary
metrics. The denominator and label coverage are always reported; an unreviewed set yields
`null`, never zero, for negative signal rate. The adjudicated subset may be selected and
correlated. Programmatic localization is scored separately from human signal labels; human
region annotations currently require expert adjudication outside the automatic scorer.
