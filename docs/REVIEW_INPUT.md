# Reviewer-confirmed input

Keep this JSON under `data/` and run `integrity-agent run ... --review-input data/review.json`.
Use IDs from the local manifest. All numbers are checked against the corresponding extracted
source text. Review the actual table relationships: numerical membership alone is insufficient.

```json
{
  "stats": [{
    "work_id": "synthetic-work", "artifact_id": "synthetic-artifact",
    "group": "Treatment", "variable": "integer scale", "mean": "1.25",
    "sd": "0.50", "n": 12, "items": 2, "scale": "average",
    "integer_scale_confirmed": true
  }],
  "baselines": [{
    "work_id": "synthetic-work", "artifact_id": "synthetic-artifact",
    "variables": ["age"], "means": [[40, 41]], "sds": [[10, 10]],
    "ns": [100, 100], "randomized": true,
    "independent_variables_confirmed": false
  }],
  "registry": [{
    "paper_artifact_id": "synthetic-artifact",
    "registry_artifact_id": "synthetic-registry",
    "paper_fields": {"enrollment": 120},
    "source_quote": "We enrolled 120 participants."
  }],
  "distributions": [{
    "artifact_id": "synthetic-csv", "column": "measurement",
    "expected_skew": false, "terminal_digits": true, "digit_resolution": 0.1
  }]
}
```

Specify sample SD rather than SE; `items` is the count of integer items averaged within
participants. For sums, use `scale: "sum"`. Missing items, weighting, transformations and
population SDs invalidate the current checks. Do not mark baseline independence true without
substantive justification. Current registry differences do not establish historical changes.
