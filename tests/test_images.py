import numpy as np
import pytest

from integrity_agent.detectors.images import compare, copy_move, detect
from integrity_agent.evaluation import manipulations, panel, synthetic_image
from integrity_agent.extraction import split_panels


@pytest.mark.parametrize(
    "kind", ["duplicate", "crop", "rotate", "flip", "scale", "contrast", "edited-features"]
)
def test_known_manipulations(kind):
    a = synthetic_image(40)
    _, b = manipulations(a)[kind]
    match = compare(panel(a, "a"), panel(b, "b", "other"))
    assert match is not None
    assert match.finding.measurements["inliers"] >= 14
    assert match.evidence.ndim == 3


def test_clone():
    _, a = manipulations(synthetic_image(40))["cloned-regions"]
    assert copy_move(panel(a, "a")) is not None


def test_unrelated_and_blank_are_not_matches():
    assert compare(panel(synthetic_image(45), "a"), panel(synthetic_image(345), "b")) is None
    assert (
        compare(
            panel(np.zeros((100, 100), dtype=np.uint8), "a"),
            panel(np.zeros((100, 100), dtype=np.uint8), "b"),
        )
        is None
    )


def test_panel_coordinates():
    a = np.zeros((100, 210), dtype=np.uint8)
    a[:, 100:110] = 255
    result = split_panels(a)
    assert len(result) == 2
    assert result[0][:4] == (0, 0, 105, 100)
    assert result[1][:4] == (105, 0, 105, 100)


def test_geometry_and_local_difference_categories():
    a = synthetic_image(40)
    for kind, expected in [("rotate", 2), ("edited-features", 3), ("cloned-regions", 3)]:
        _, b = manipulations(a)[kind]
        assert (
            compare(panel(a, "a"), panel(b, "b", "other")).finding.measurements["category"]
            == expected
        )


def test_cached_batch_preserves_finding_and_evidence():
    a = panel(synthetic_image(40), "a")
    _, pixels = manipulations(a.pixels)["flip"]
    b = panel(pixels, "b", "other")
    direct = compare(a, b)
    cached = next(m for m in detect([a, b]) if m.finding.kind == "image-reuse")
    assert cached.finding == direct.finding
    assert np.array_equal(cached.evidence, direct.evidence)
