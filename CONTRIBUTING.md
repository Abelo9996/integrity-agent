# Contributing

Use Python 3.11+ and uv. Run `uv sync --dev`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy`, and `uv run pytest` before a pull request.
Tests must be offline and use synthetic data. Never commit an individual researcher's report,
credentials, downloaded papers, caches or run output. Add a regression test for a substantive bug.

See [adding a detector](docs/adding-a-detector.md). Detectors must be deterministic,
return typed evidence, declare assumptions, and perform no network operations.
