"""Procedural stress fixtures with known locations; never clinical ground truth.

Development seeds: 20–23. Frozen evaluation seeds: 3000–3019.
Shared typography/independent bands are intentional hard negatives.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RegionCase:
    name: str
    source: np.ndarray
    target: np.ndarray
    source_box: tuple[int, int, int, int]
    target_box: tuple[int, int, int, int]


def blot_figure(seed: int) -> np.ndarray:
    """Independently varying smooth bands, grain and common figure annotations."""
    rng = np.random.default_rng(seed)
    h, w = 480, 720
    a = rng.normal(224, 2.5, (h, w))
    yy, xx = np.mgrid[:h, :w]
    a += 3 * np.sin(xx / 170) + 2 * np.cos(yy / 110)
    for cy in (110, 215, 320):
        for cx in range(90, 680, 95):
            sx, sy = rng.uniform(9, 16), rng.uniform(2.5, 5.5)
            dx, dy = rng.uniform(-3, 3, 2)
            band = np.exp(-(((xx - cx - dx) / sx) ** 4) - ((yy - cy - dy) / sy) ** 2)
            a -= rng.uniform(65, 145) * band
    a = np.clip(a, 0, 255).astype(np.uint8)
    # These repeat between independent images and must not support a reuse claim.
    a[:55] = 255
    a[385:] = 255
    cv2.putText(
        a, "A   CONTROL   TREATMENT", (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 1, cv2.LINE_AA
    )
    for i in range(6):
        cv2.putText(
            a, "Sample 123", (15 + i * 115, 415), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1, cv2.LINE_AA
        )
    return a


def layout_figure(seed: int, kind="table") -> np.ndarray:
    """No copied experimental pixels: only recurring labels, rules and symbols."""
    rng = np.random.default_rng(seed)
    a = np.full((420, 640), 255, np.uint8)
    if kind == "table":
        for row in range(7):
            cv2.putText(
                a,
                "Mean SD Sample N",
                (20, 42 + 51 * row),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                0,
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                a,
                f"{rng.uniform(1, 99):.2f}",
                (410, 42 + 51 * row),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                0,
                1,
                cv2.LINE_AA,
            )
            cv2.line(a, (18, 50 + 51 * row), (610, 50 + 51 * row), 0, 1)
    else:
        for dx in (0, 320):
            for dy in (0, 210):
                cv2.line(a, (35 + dx, 25 + dy), (35 + dx, 175 + dy), 0, 1)
                cv2.line(a, (35 + dx, 175 + dy), (295 + dx, 175 + dy), 0, 1)
                cv2.putText(
                    a,
                    "Control 123",
                    (65 + dx, 198 + dy),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    0,
                    1,
                    cv2.LINE_AA,
                )
                for x in (65, 130, 195):
                    top = int(rng.integers(45, 145)) + dy
                    cv2.rectangle(a, (x + dx, top), (x + 28 + dx, 174 + dy), 0, 1)
                    for y in range(top + 3, 172 + dy, 5):
                        cv2.line(a, (x + dx, y), (x + 28 + dx, y), 0, 1)
    return a


def region_cases(seed: int) -> list[RegionCase]:
    a = blot_figure(seed)
    # 64x30 = 0.56% of the figure; the dark band occupies substantially less.
    box_a = (58, 95, 64, 30)
    box_b = (438, 305, 64, 30)
    x, y, w, h = box_a
    x2, y2, _, _ = box_b
    patch = a[y : y + h, x : x + w].copy()
    out = []
    for kind in ("copy", "flip", "contrast", "jpeg"):
        b = a.copy()
        transplant = np.fliplr(patch) if kind == "flip" else patch
        if kind == "contrast":
            transplant = np.clip(transplant.astype(float) * 0.8 + 20, 0, 255).astype(np.uint8)
        b[y2 : y2 + h, x2 : x2 + w] = transplant
        if kind == "jpeg":
            ok, encoded = cv2.imencode(".jpg", b, [cv2.IMWRITE_JPEG_QUALITY, 95])
            assert ok
            b = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
        out.append(RegionCase(kind, a, b, box_a, box_b))
    b = blot_figure(seed + 100_000)
    b[y2 : y2 + h, x2 : x2 + w] = patch
    out.append(RegionCase("cross-paper", a, b, box_a, box_b))
    return out


def localized(match, case: RegionCase) -> bool:
    """Require at least four correspondence points in BOTH injected regions."""
    if match is None:
        return False
    measurements = match.finding.measurements
    src = np.asarray(measurements.get("source_points", []))
    dst = np.asarray(measurements.get("target_points", []))
    if src.ndim != 2 or dst.shape != src.shape:
        return False

    def inside(points, box):
        x, y, w, h = box
        return (
            (points[:, 0] >= x)
            & (points[:, 0] <= x + w)
            & (points[:, 1] >= y)
            & (points[:, 1] <= y + h)
        )

    direct = inside(src, case.source_box) & inside(dst, case.target_box)
    reverse = inside(src, case.target_box) & inside(dst, case.source_box)
    return bool(max(int(direct.sum()), int(reverse.sum())) >= 4)
