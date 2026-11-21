"""D1: transform-aware hash retrieval, SIFT/RANSAC verification and copy-move.

Pure array operations. Similarity is evidence of shared visual content, never intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import cv2
import imagehash
import numpy as np
from PIL import Image

from ..models import Finding, finding


@dataclass
class Panel:
    id: str
    work_id: str
    artifact_id: str
    pixels: np.ndarray
    caption: str = ""
    box: tuple[int, int, int, int] | None = None


@dataclass
class Match:
    finding: Finding
    evidence: np.ndarray


def gray(pixels):
    a = np.asarray(pixels, dtype=np.uint8)
    if a.ndim == 3:
        a = cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2GRAY)
    if max(a.shape) > 900:
        scale = 900 / max(a.shape)
        a = cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(a)


def variants(a):
    for flip in (False, True):
        b = np.fliplr(a) if flip else a
        for rotation in range(4):
            yield np.ascontiguousarray(np.rot90(b, rotation)), flip, rotation


def hashes(a):
    return [
        (
            imagehash.phash(Image.fromarray(v)),
            imagehash.dhash(Image.fromarray(v)),
            imagehash.whash(Image.fromarray(v)),
        )
        for v, _, _ in variants(a)
    ]


def hash_distance(ha, hb):
    return min(min(int(x - y) for x, y in zip(a, b, strict=True)) for a in ha for b in hb)


def features(a):
    return cv2.SIFT_create(nfeatures=2500, contrastThreshold=0.025).detectAndCompute(a, None)


def good_matches(da, db):
    if da is None or db is None or len(da) < 3 or len(db) < 3:
        return []
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    # One target keypoint per match prevents inflated counts from many-to-one matches.
    candidates = sorted(
        [m for pair in pairs if len(pair) == 2 for m, n in [pair] if m.distance < 0.7 * n.distance],
        key=lambda m: m.distance,
    )
    used = set()
    result = []
    for m in candidates:
        if m.trainIdx not in used:
            result.append(m)
            used.add(m.trainIdx)
    return result


def overlay(a, b, src, dst):
    canvas = np.full((max(a.shape[0], b.shape[0]), a.shape[1] + b.shape[1], 3), 255, np.uint8)
    canvas[: a.shape[0], : a.shape[1]] = cv2.cvtColor(a, cv2.COLOR_GRAY2RGB)
    canvas[: b.shape[0], a.shape[1] :] = cv2.cvtColor(b, cv2.COLOR_GRAY2RGB)
    for p, q in zip(src[:: max(1, len(src) // 35)], dst[:: max(1, len(dst) // 35)], strict=True):
        p = tuple(np.int32(p))
        q = tuple(np.int32(q + [a.shape[1], 0]))
        cv2.circle(canvas, p, 3, (0, 190, 100), 1)
        cv2.circle(canvas, q, 3, (0, 190, 100), 1)
        cv2.line(canvas, p, q, (220, 70, 30), 1)
    return canvas


def local_differences(source, target, matrix):
    """Measure localized residual regions after alignment and global brightness fitting."""
    aligned = cv2.warpPerspective(source, matrix, (target.shape[1], target.shape[0]))
    valid = (
        cv2.warpPerspective(
            np.ones_like(source, dtype=np.uint8), matrix, (target.shape[1], target.shape[0])
        )
        > 0
    )
    valid = cv2.erode(valid.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    if valid.sum() < 1000:
        return {"fraction": 0.0, "largest_region": 0, "localized": False}
    x = aligned[valid].astype(float)
    y = target[valid].astype(float)
    design = np.column_stack((x, np.ones(len(x))))
    keep = np.ones(len(x), bool)
    coefficients = np.array([1.0, 0.0])
    for _ in range(3):
        coefficients = np.linalg.lstsq(design[keep], y[keep], rcond=None)[0]
        residual = np.abs(design @ coefficients - y)
        keep = residual <= max(8, float(np.quantile(residual, 0.8)))
    errors = np.abs(aligned.astype(float) * coefficients[0] + coefficients[1] - target)
    threshold = max(30, float(np.median(errors[valid])) * 4)
    mask = ((errors > threshold) & valid).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, regions, _ = cv2.connectedComponentsWithStats(mask)
    largest = int(max(regions[1:, cv2.CC_STAT_AREA], default=0))
    fraction = float(mask[valid].mean())
    return {
        "fraction": fraction,
        "largest_region": largest,
        "localized": bool(
            0.01 < fraction < 0.25
            and largest > max(300, 0.008 * valid.sum())
            and largest / max(1, int(mask.sum())) > 0.5
        ),
        "region_concentration": largest / max(1, int(mask.sum())),
        "threshold": threshold,
    }


def compare(
    a: Panel, b: Panel, *, min_inliers=14, min_ratio=0.55, cached_a=None, cached_b=None
) -> Match | None:
    aa, bb = gray(a.pixels), gray(b.pixels)
    if min(np.std(aa), np.std(bb)) < 7 or min(*aa.shape, *bb.shape) < 48:
        return None
    ha, ka, da = cached_a or (hashes(aa), *features(aa))
    hb, kb, db = cached_b or (hashes(bb), *features(bb))
    distance = hash_distance(ha, hb)
    best = None
    for flipped in (False, True):
        target = np.ascontiguousarray(np.fliplr(bb)) if flipped else bb
        k2, d2 = features(target) if flipped else (kb, db)
        matches = good_matches(da, d2)
        # Descriptor retrieval rescues crops that global hashes cannot shortlist.
        if distance > 12 and len(matches) < min_inliers:
            continue
        if len(matches) < min_inliers:
            continue
        src = np.float32([ka[m.queryIdx].pt for m in matches])
        dst = np.float32([k2[m.trainIdx].pt for m in matches])
        cv2.setRNGSeed(0)
        matrix, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        if matrix is None or mask is None or not np.isfinite(matrix).all():
            continue
        inliers = mask.ravel().astype(bool)
        count = int(inliers.sum())
        ratio = count / len(matches)
        if count < min_inliers or ratio < min_ratio:
            continue
        src, dst = src[inliers], dst[inliers]
        coverage_a = cv2.contourArea(cv2.convexHull(src)) / aa.size
        coverage_b = cv2.contourArea(cv2.convexHull(dst)) / bb.size
        if min(coverage_a, coverage_b) < 0.025:
            continue
        corners = np.float32(
            [[0, 0], [aa.shape[1], 0], [aa.shape[1], aa.shape[0]], [0, aa.shape[0]]]
        )
        projected = cv2.perspectiveTransform(corners[None], matrix)[0]
        if not cv2.isContourConvex(projected):
            continue
        exact = not flipped and aa.shape == bb.shape and np.array_equal(a.pixels, b.pixels)
        category = 1 if exact else 2
        if best is None or count > best[0]:
            best = count, ratio, src, dst, target, flipped, category, coverage_a, coverage_b, matrix
    if best is None:
        return None
    count, ratio, src, dst, target, flipped, category, ca, cb, matrix = best
    differences = local_differences(aa, target, matrix) if category != 1 else {"localized": False}
    if differences["localized"]:
        category = 3
    f = finding(
        "D1",
        "image-reuse",
        "info" if a.work_id == b.work_id else "review" if category == 1 else "strong",
        [a.work_id, b.work_id],
        [a.artifact_id, b.artifact_id],
        f"Panels {a.id} and {b.id} contain spatially consistent visual matches; warrants review.",
        parameters={
            "min_inliers": min_inliers,
            "min_ratio": min_ratio,
            "ransac_px": 3.0,
            "hash_cutoff": 12,
            "normalization": "CLAHE",
            "sift_ratio": 0.7,
        },
        measurements={
            "category": category,
            "aligned_local_differences": differences,
            "inliers": count,
            "inlier_ratio": ratio,
            "hash_distance": distance,
            "flipped_for_match": flipped,
            "coverage_a": ca,
            "coverage_b": cb,
            "homography": matrix.tolist(),
            "panel_ids": [a.id, b.id],
        },
        limitations=[
            "Bik-style category describes geometry, not intent; category 2 includes benign resizing.",
            "Category 3 local differences may also reflect annotations, compression or resampling; examine original images.",
            "Check attribution, shared controls, review republication, versions and corrections.",
            "Matching regions can be small; captions and original figures require inspection.",
        ],
    )
    return Match(f, overlay(aa, target, src, dst))


def copy_move(panel: Panel, *, min_matches=10) -> Match | None:
    a = gray(panel.pixels)
    kp, des = features(a)
    if des is None or len(des) < 20:
        return None
    clusters = {}
    for i, neighbors in enumerate(cv2.BFMatcher().knnMatch(des, des, k=min(8, len(des)))):
        eligible = [
            m
            for m in neighbors
            if m.trainIdx != i and np.linalg.norm(np.array(kp[i].pt) - kp[m.trainIdx].pt) > 30
        ]
        if len(eligible) < 2 or eligible[0].distance >= 0.65 * eligible[1].distance:
            continue
        m = eligible[0]
        p, q = np.array(kp[i].pt), np.array(kp[m.trainIdx].pt)
        delta = q - p
        if delta[0] < 0 or (delta[0] == 0 and delta[1] < 0):
            p, q, delta = q, p, -delta
        key = tuple(np.round(delta / 5).astype(int))
        clusters.setdefault(key, {})[(tuple(p), tuple(q))] = (p, q)
    if not clusters:
        return None
    pairs = list(max(clusters.values(), key=len).values())
    if len(pairs) < min_matches:
        return None
    src, dst = np.float32([p for p, _ in pairs]), np.float32([q for _, q in pairs])
    area = cv2.contourArea(cv2.convexHull(src))
    if area < 0.005 * a.size:
        return None
    f = finding(
        "D1",
        "copy-move",
        "strong",
        [panel.work_id],
        [panel.artifact_id],
        f"Panel {panel.id} contains repeated spatially separated regions consistent with duplication.",
        parameters={"min_matches": min_matches, "displacement_bin_px": 5, "ratio": 0.65},
        measurements={
            "category": 3,
            "matches": len(pairs),
            "source_points": src.tolist(),
            "target_points": dst.tolist(),
            "panel_id": panel.id,
        },
        limitations=[
            "Natural repeating structure and assembly of figure panels can produce this signal.",
            "Translation-based copy-move only; rotated, blended or very small clones can be missed.",
        ],
    )
    return Match(f, overlay(a, a, src, dst))


def detect(panels: list[Panel]) -> list[Match]:
    results = []
    cache = {}
    for p in panels:
        a = gray(p.pixels)
        cache[p.id] = (hashes(a), *features(a))
        m = copy_move(p)
        if m:
            results.append(m)
    for a, b in combinations(panels, 2):
        if a.artifact_id == b.artifact_id:
            continue
        m = compare(a, b, cached_a=cache[a.id], cached_b=cache[b.id])
        if m:
            results.append(m)
    return results
