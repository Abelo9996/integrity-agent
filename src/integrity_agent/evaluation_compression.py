"""New procedural families and layouts, frozen before the compression iteration.

Development: seeds60–62, fixed cells/lanes. Holdout: seeds41000–41007,
jittered lanes and a different spatial layout. This is not biological validation.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class CompressionCase:
    name: str
    family: str
    source: np.ndarray
    target: np.ndarray
    source_box: tuple[int, int, int, int]
    target_box: tuple[int, int, int, int]


def jpeg(a, quality):
    ok, encoded = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, quality])
    assert ok
    return cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)


def patch(seed, family):
    rng = np.random.default_rng(seed)
    h, w = (40, 72) if family == "lanes" else (64, 64)
    yy, xx = np.mgrid[:h, :w]
    coarse = cv2.resize(
        rng.normal(0, 3, (8, 12)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC
    )
    a = 223 + coarse + rng.normal(0, 1.8, (h, w))
    if family == "lanes":
        center = h * 0.5 + 1.6 * np.sin(xx / rng.uniform(5, 10)) + rng.uniform(-1, 1)
        envelope = np.exp(
            -(((xx - w * 0.5) / rng.uniform(18, 23)) ** 6)
            - ((yy - center) / rng.uniform(4, 6)) ** 2
        )
        modulation = cv2.resize(
            rng.uniform(0.65, 1.2, (5, 12)).astype(np.float32),
            (w, h),
            interpolation=cv2.INTER_CUBIC,
        )
        a -= 110 * envelope * modulation
    else:
        for _ in range(9):
            x, y = rng.integers(12, w - 12), rng.integers(12, h - 12)
            a -= rng.uniform(25, 65) * np.exp(
                -(((xx - x) / rng.uniform(3, 8)) ** 2) - ((yy - y) / rng.uniform(3, 8)) ** 2
            )
    return np.clip(a, 0, 255).astype(np.uint8)


def figure(seed, family, *, holdout=False, twins=False):
    rng = np.random.default_rng(seed)
    h, w = (1000, 1600) if holdout else (900, 1440)
    coarse = cv2.resize(
        rng.normal(0, 2, (36, 48)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC
    )
    a = np.clip(225 + coarse + rng.normal(0, 1, (h, w)), 0, 255).astype(np.uint8)
    positions = [(130 + col * 270, 120 + row * 230) for row in range(3) for col in range(5)]
    if holdout:
        positions = [
            (x + int(rng.integers(-35, 35)), y + int(rng.integers(-45, 45))) for x, y in positions
        ]
    boxes = []
    for i, (x, y) in enumerate(positions):
        p = patch(seed * 100 + i, family)
        if twins:
            # Equal smooth envelopes with independent noise are intentional negatives.
            yy, xx = np.mgrid[: p.shape[0], : p.shape[1]]
            envelope = np.exp(
                -(((xx - p.shape[1] / 2) / 18) ** 4) - ((yy - p.shape[0] / 2) / 5) ** 2
            )
            p = np.clip(224 - 110 * envelope + rng.normal(0, 2.5, p.shape), 0, 255).astype(np.uint8)
        a[y : y + p.shape[0], x : x + p.shape[1]] = p
        boxes.append((x, y, p.shape[1], p.shape[0]))
    a[:70] = 255
    for x in (30, 490, 950):
        cv2.putText(
            a, "Sample CONTROL 123", (x, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 0, 1, cv2.LINE_AA
        )
    return a, boxes


def cases(seed, family, *, holdout=False):
    a, boxes = figure(seed, family, holdout=holdout)
    x, y, w, h = boxes[1]
    tx, ty, _, _ = boxes[-2]
    crop = a[y : y + h, x : x + w]
    out = []
    for kind in ("native", "jpeg95", "jpeg85", "jpeg75", "recompressed", "scaled"):
        scale = 1.25 if kind == "scaled" else 1
        inserted = (
            cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            if scale != 1
            else crop
        )
        b = a.copy()
        b[ty : ty + inserted.shape[0], tx : tx + inserted.shape[1]] = inserted
        if kind.startswith("jpeg"):
            b = jpeg(b, int(kind[4:]))
        elif kind == "recompressed":
            b = jpeg(jpeg(b, 90), 80)
        out.append(
            CompressionCase(
                kind, family, a, b, (x, y, w, h), (tx, ty, inserted.shape[1], inserted.shape[0])
            )
        )
    return out


def localized(match, case):
    if match is None:
        return False
    m = match.finding.measurements
    src = np.asarray(m.get("source_figure_points", []))
    dst = np.asarray(m.get("target_figure_points", []))
    if src.ndim != 2 or src.shape != dst.shape:
        return False

    def inside(points, box):
        x, y, w, h = box
        return (
            (points[:, 0] >= x)
            & (points[:, 0] < x + w)
            & (points[:, 1] >= y)
            & (points[:, 1] < y + h)
        )

    return bool(
        max(
            (inside(src, case.source_box) & inside(dst, case.target_box)).sum(),
            (inside(dst, case.source_box) & inside(src, case.target_box)).sum(),
        )
        >= 4
    )
