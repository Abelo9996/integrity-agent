from decimal import Decimal
from itertools import product

import numpy as np
import pytest

from integrity_agent.detectors.stats import baseline_dispersion, grim, grimmer
from integrity_agent.models import Baseline


def test_grim_known_cases():
    assert grim("1.25", 4)
    assert not grim("1.26", 4)
    assert grim("1.125", 4, 2)
    assert not grim("1.125", 4, 1)
    assert grim("-1.25", 4)
    assert grim("1.2", 4)  # inclusive ties are conservative


def test_grimmer_known_cases():
    assert grimmer("2.00", "1.00", 3)  # 1,2,3
    assert not grimmer("2.00", "0.10", 3)
    assert grimmer("1.00", "0.50", 3, 2)  # item averages .5,1,1.5
    assert not grimmer("1.00", "0.50", 3, 1)


def test_small_integer_samples_never_false_flag():
    for values in product(range(4), repeat=4):
        for items in (1, 2, 3):
            a = np.array(values) / items
            mean = f"{a.mean():.3f}"
            sd = f"{a.std(ddof=1):.3f}"
            assert grim(mean, 4, items)
            assert grimmer(mean, sd, 4, items) is True


def baseline(means):
    return Baseline(
        work_id="w",
        artifact_id="a",
        variables=["age"],
        means=[means],
        sds=[[10, 10]],
        ns=[100, 100],
        randomized=True,
    )


def test_baseline_over_and_under_dispersion():
    assert baseline_dispersion(baseline([10, 50]))[0].kind == "over-dispersion"
    assert baseline_dispersion(baseline([10, 10]))[0].kind == "under-dispersion"
    assert baseline_dispersion(baseline([10, 11])) == []
    assert baseline_dispersion(baseline([10, 50])) == baseline_dispersion(baseline([10, 50]))


def test_baseline_rejects_invalid():
    b = baseline([10, 20])
    b.sds = [[0, 1]]
    with pytest.raises(ValueError):
        baseline_dispersion(b)


def test_rounding_precision_preserved():
    assert Decimal("1.00").as_tuple().exponent == -2
    assert not grim("1.01", 10)
