# Adding a detector

1. Add a module under `src/integrity_agent/detectors/`. Accept typed values or arrays:
   do not fetch URLs, read environment variables, write files or invoke a model.
2. State preconditions and abstain when they are unverified. Return `Finding` objects
   using `models.finding()` so IDs are reproducible from detector inputs and outputs.
3. Include detector name, kind, tier, work/artifact IDs, measured values, thresholds,
   algorithm settings, and limitations. Statements must describe observations rather
   than intent. A strength tier measures evidence strength, not a person's reliability.
4. Return visualization arrays alongside findings when useful. The pipeline writes
   images under `outputs/<run>/evidence/` and adds relative paths to findings.
5. Register artifact eligibility in `agent.plan()` and call the detector from
   `pipeline.analyze()`. Record skipped prerequisites in collection coverage.
6. Add offline synthetic tests: known positive, plausible benign case, boundary,
   missing input, stable ID, and parameter change. Measure false positives as well
   as recall; do not tune against a final held-out benchmark.
7. Feed findings into the report verifier. Do not construct report claims directly
   from model prose. Verify exact statement/tier/artifact association and source SHA-256.

The optional provider implements `Provider.select()` and `Provider.extract_pdf()`.
A different provider can be passed to `analyze(provider=..., llm=True)`. Provider output
is untrusted. Source-verified extracted values are still subject to detector assumptions;
the existence of a number in a paper does not prove its statistical interpretation.

Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and
`uv run mypy`. Never add a real researcher's output as a regression fixture.
