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
checks Python 3.11 and 3.12, including 60 tests, lint, types, the demo and Git-history hygiene.
A small CC BY PMC pilot now complements the procedural smoke benchmark: paired category-2/3
recall was 100% with 0/35 unrelated-pair matches, but standalone clone recall was 81.82%
and 4/11 unmodified figures triggered review signals. See the evaluation caveats.
A bounded private sanity check has run; individual reports and review notes remain local.
It does not establish reliable screening. Broader source coverage, discrimination of ordinary
text/graph repetition, small-blot sensitivity and independent expert adjudication remain necessary.

Use `--llm` to enable Anthropic structured PDF extraction and finding prioritization;
without it the complete evidence/report pipeline remains deterministic. Models cannot
create report findings. Provider failures are logged without suppressing image extraction.
Use [review input](docs/REVIEW_INPUT.md) for statistical assumptions and registry comparisons.

Useful options: `--name`, `--openalex-id`, `--confirm-author A...` (explicit candidate
confirmation for scripted runs), `--max-works N` (recorded coverage limit),
`--no-with-retraction-watch`, and `--no-with-field-baseline`. Reports are local-only;
the CLI never uploads them or sends concerns to journals.
