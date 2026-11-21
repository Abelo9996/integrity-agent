"""D2/D3: conservative rounding-lattice tests and baseline dispersion simulation."""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from itertools import combinations

import numpy as np

from ..models import Baseline, Stat, finding


def interval(value: str):
    d = Decimal(value)
    half = Decimal(10) ** d.as_tuple().exponent / 2
    return d - half, d + half


def integer_bounds(low, high):
    return int(low.to_integral_value(rounding=ROUND_CEILING)), int(
        high.to_integral_value(rounding=ROUND_FLOOR)
    )


def grim(mean: str, n: int, items: int = 1) -> bool:
    if n < 1 or items < 1:
        raise ValueError("n and items must be positive")
    lo, hi = interval(mean)
    a, b = integer_bounds(lo * n * items, hi * n * items)
    return a <= b


def grimmer(mean: str, sd: str, n: int, items: int = 1) -> bool | None:
    """Necessary mean/SD lattice + parity test, with conservative inclusive rounding ties.

    For integer totals y_i: S=sum(y), Q=sum(y²), Q ≡ S (mod 2).
    Sample variance of item averages is (nQ-S²)/(n(n-1)k²).
    True means not rejected, not proof an integer sample exists. None means computation cap.
    """
    if n < 2 or items < 1 or Decimal(sd) < 0:
        raise ValueError("Invalid sample SD inputs")
    ml, mh = interval(mean)
    sl, sh = interval(sd)
    sl = max(sl, Decimal(0))
    a, b = integer_bounds(ml * n * items, mh * n * items)
    if b - a > 100_000:
        return None
    for total in range(a, b + 1):
        scale = Decimal(n - 1) * items**2
        ql = sl**2 * scale + Decimal(total * total) / n
        qh = sh**2 * scale + Decimal(total * total) / n
        q0, q1 = integer_bounds(ql, qh)
        q0 += (total - q0) % 2
        # Tight minimum sum of squares at fixed integer total.
        base, remainder = divmod(total, n)
        qmin = (n - remainder) * base**2 + remainder * (base + 1) ** 2
        q0 = max(q0, qmin)
        q0 += (total - q0) % 2
        if q0 <= q1:
            return True
    return False


def detect_summary(stats: list[Stat]):
    findings = []
    for s in stats:
        if not s.integer_scale_confirmed:
            continue
        k = s.items if s.scale == "average" else 1
        args = {
            "n": s.n,
            "items": k,
            "mean": s.mean,
            "rounding": "inclusive half-unit interval",
            "group": s.group,
            "variable": s.variable,
        }
        if not grim(s.mean, s.n, k):
            findings.append(
                finding(
                    "D2",
                    "grim",
                    "review",
                    [s.work_id],
                    [s.artifact_id],
                    f"Reported mean for {s.variable} ({s.group}) is inconsistent with the specified integer scale and sample size.",
                    parameters=args,
                    measurements={"mean": s.mean},
                    limitations=[
                        "Requires complete integer item responses and the stated sample size; weighting and missing items invalidate assumptions."
                    ],
                )
            )
        elif s.sd is not None and grimmer(s.mean, s.sd, s.n, k) is False:
            findings.append(
                finding(
                    "D2",
                    "grimmer",
                    "review",
                    [s.work_id],
                    [s.artifact_id],
                    f"Reported mean and sample SD for {s.variable} ({s.group}) fail the integer moment lattice check.",
                    parameters={**args, "sd": s.sd},
                    limitations=[
                        "Sample SD, not SE or population SD, is assumed.",
                        "Passing is only a necessary consistency condition; transformed scores are ineligible.",
                    ],
                )
            )
    for a, b in combinations(stats, 2):
        if (a.work_id, a.group, a.variable) == (b.work_id, b.group, b.variable):
            continue
        if a.sd and b.sd and (a.mean, a.sd) == (b.mean, b.sd):
            findings.append(
                finding(
                    "D2",
                    "identical-summary-pair",
                    "info",
                    [a.work_id, b.work_id],
                    [a.artifact_id, b.artifact_id],
                    "Identical reported mean and SD pairs occur in distinct groups or papers.",
                    measurements={"mean": a.mean, "sd": a.sd, "groups": [a.group, b.group]},
                    limitations=[
                        "Coincidence, coarse rounding or the same cohort may explain this."
                    ],
                )
            )
    return findings


def baseline_dispersion(table: Baseline, *, simulations=20000, seed=0, alpha=0.001):
    if not table.randomized:
        return []
    means, sd, ns = (
        np.array(table.means, float),
        np.array(table.sds, float),
        np.array(table.ns, float),
    )
    if (
        means.ndim != 2
        or means.shape != sd.shape
        or means.shape[1] != len(ns)
        or means.shape[0] != len(table.variables)
    ):
        raise ValueError("Baseline dimensions do not agree")
    if (
        len(ns) < 2
        or (ns <= 1).any()
        or (sd <= 0).any()
        or not np.isfinite(means).all()
        or not np.isfinite(sd).all()
    ):
        raise ValueError("Baseline requires finite means, positive SDs and group sizes >1")
    if simulations < 1000:
        raise ValueError("At least 1000 simulations are required")
    weights = ns[None, :] / sd**2
    center = np.sum(means * weights, axis=1) / weights.sum(axis=1)
    observed = np.sum(weights * (means - center[:, None]) ** 2, axis=1)
    rng = np.random.default_rng(seed)
    draws = rng.normal(size=(simulations, *means.shape)) / np.sqrt(weights)[None, :, :]
    centers = np.sum(draws * weights, axis=2) / weights.sum(axis=1)
    null = np.sum(weights * (draws - centers[:, :, None]) ** 2, axis=2)
    result = []
    tests = [(table.variables[i], observed[i], null[:, i]) for i in range(len(observed))]
    if table.independent_variables_confirmed:
        tests.append(("combined independent variables", observed.sum(), null.sum(axis=1)))
    for variable, value, reference in tests:
        lower = (1 + np.count_nonzero(reference <= value)) / (simulations + 1)
        upper = (1 + np.count_nonzero(reference >= value)) / (simulations + 1)
        adjusted = min(1.0, 2 * min(lower, upper) * len(tests))
        if adjusted < alpha:
            direction = "under-dispersion" if lower < upper else "over-dispersion"
            result.append(
                finding(
                    "D3",
                    direction,
                    "review",
                    [table.work_id],
                    [table.artifact_id],
                    f"Baseline {variable} shows {direction} under the stated randomization model.",
                    parameters={
                        "simulations": simulations,
                        "seed": seed,
                        "alpha": alpha,
                        "multiplicity": len(tests),
                        "model": "normal group means; plug-in standard errors",
                    },
                    measurements={"statistic": float(value), "adjusted_two_sided_p": adjusted},
                    limitations=[
                        "Carlisle-style approximation, not a replication of a validated clinical audit.",
                        "Rounding, stratification, correlations, non-normality and unequal variances may affect calibration.",
                        "No combined statistic without explicit independence confirmation.",
                    ],
                )
            )
    return result
