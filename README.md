# Research Integrity Agent

A prototype evidence-gathering assistant for expert integrity reviewers. It collects
identifier-linked open artifacts, runs deterministic checks, and produces local HTML and JSON
reports. It does not assess intent or decide whether a person committed misconduct.

**Anomalies are not proof of misconduct. Findings require expert human review.**

## Quick start

```sh
git clone https://github.com/Abelo9996/integrity-agent.git
cd integrity-agent
uv sync --dev
uv run integrity-agent demo
cp .env.example .env
# Set INTEGRITY_CONTACT_EMAIL and OPENALEX_API_KEY in .env.
uv run integrity-agent run --orcid <ORCID>
```

The CLI shows author candidates and requires the exact OpenAlex author ID to confirm selection.
Every report claim is reconstructed from a detector finding and checked before rendering.
Schema 1.2 rejects ambiguous IDs and checks source/evidence files against recorded hashes;
see [evidence verification](docs/EVIDENCE_VERIFICATION.md). Per-paper runtime coverage
distinguishes completed, missing and failed checks. Equivalent verified image evidence is
grouped for review while every raw finding/claim remains in JSON. Each run records detector
and input hashes, dependency versions and the selected image profile.
Run artifacts live in ignored `outputs/`, `cache/`, and `data/` folders. Never publish reports
about individuals. See [responsible use](RESPONSIBLE_USE.md).

## Development

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run integrity-agent evaluate-images
```

See [API audit](docs/API_STATUS.md), [detector guide](docs/adding-a-detector.md), and
[limitations](docs/LIMITATIONS.md). Source code is Apache-2.0. Dependencies retain their own
licenses; in particular PyMuPDF is AGPL/commercial, which matters for redistribution.

## Limitations

Works best on biomedical papers with open full text. It misses problems that leave no trace
in public artifacts. Screening patterns reflect documented cases involving people who got
caught, which introduces selection bias; this prototype itself is not a trained classifier.
Incomplete coverage, correlated variables, reused controls, attributed review figures,
preprint versions and corrections can all affect interpretation. No detector measures intent.

## Current prototype status

This is a prototype implementation, not a completed validation study. The offline demo and
mocked ORCID workflow produce verified HTML/JSON. See [milestone status](docs/MILESTONES.md)
and [evaluation protocol](docs/EVALUATION.md) for what has and has not been tested.
The [CI workflow](https://github.com/Abelo9996/integrity-agent/actions/workflows/ci.yml)
checks Python 3.11 and 3.12, including tests, lint, types, the demo and Git-history hygiene.
The default image profile localizes 76/80 uncompressed small copies in held-out procedural
fixtures, with 0/120 negative-test signals, but only 5/20 JPEG-compressed copies. On the
small CC BY PMC regression corpus, paired category-2 detection falls to 92.73%, category-3
detection remains 100%, and standalone clone localization is 8/11. Four of 11 unmodified
figures still trigger signals. See the [measured tradeoffs](docs/EVALUATION.md); these
small, dependent benchmarks do not establish biomedical sensitivity or specificity.
An explicit `--experimental-compression` profile localizes 81/96 new procedural cases
(84.4%) with 0/64 constructed-negative signals, but regresses on older small bands and
compressed cell-like cases. It remains opt-in; see [complete tradeoffs](docs/COMPRESSION_ITERATION.md).
The [independent-review workflow](docs/INDEPENDENT_REVIEW.md) now creates blinded packets
and refuses to treat pending labels as negatives. Independent expert review remains pending.
A bounded private sanity check has run; individual reports and review notes remain local.
It does not establish reliable screening. Text/graph filtering and a small-region search are
implemented, but compression, smooth images, source coverage and independent expert
adjudication remain unresolved. Private reports were not rerun for the latest iteration.

Use `--llm` to enable Anthropic structured PDF extraction and finding prioritization;
without it the complete evidence/report pipeline remains deterministic. Models cannot
create report findings. Provider failures are logged without suppressing image extraction.
Use [review input](docs/REVIEW_INPUT.md) for statistical assumptions and registry comparisons.

Useful options: `--name`, `--openalex-id`, `--confirm-author A...` (explicit candidate
confirmation for scripted runs), `--max-works N` (recorded coverage limit),
`--no-with-retraction-watch`, and `--no-with-field-baseline`. Reports are local-only;
the CLI never uploads them or sends concerns to journals.
