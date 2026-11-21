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
from .image_regions import (
    TEXTURE_PARAMETERS,
    luminance,
    pixel_match,
    region_parameters,
    regions,
    supported_features,
)


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
    return cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(luminance(pixels))


def variants(a):
    for flip in (False, True):
        b = np.fliplr(a) if flip else a
        for rotation in range(4):
            yield np.ascontiguousarray(np.rot90(b, rotation)), flip, rotation


def hashes(a):
    def bits(value):
        return int.from_bytes(np.packbits(value.hash).tobytes(), "big")

    return [
        (
            bits(imagehash.phash(Image.fromarray(v))),
            bits(imagehash.dhash(Image.fromarray(v))),
            bits(imagehash.whash(Image.fromarray(v))),
        )
        for v, _, _ in variants(a)
    ]


def hash_distance(ha, hb):
    return min((x ^ y).bit_count() for a in ha for b in hb for x, y in zip(a, b, strict=True))


def features(a, raw=None):
    kp, des = cv2.SIFT_create(nfeatures=2500, contrastThreshold=0.025).detectAndCompute(a, None)
    return supported_features(a if raw is None else raw, kp, des)


def coordinates(panel, shape, points):
    """Map normalized, unflipped detector coordinates to original figure pixels."""
    h, w = panel.pixels.shape[:2]
    points = points * [w / shape[1], h / shape[0]]
    if panel.box:
        points = points + panel.box[:2]
    return points.tolist()


def pixel_finding(
    a,
    b,
    *,
    same_image=False,
    raw_a=None,
    raw_b=None,
    proposals_a=None,
    proposals_b=None,
    compression=False,
):
    params = region_parameters(compression)
    aa = luminance(a.pixels, params["max_image_side"]) if raw_a is None else raw_a
    bb = (
        luminance(b.pixels, region_parameters(compression)["max_image_side"])
        if raw_b is None
        else raw_b
    )
    result = pixel_match(
        aa,
        bb,
        same_image=same_image,
        proposals_a=proposals_a,
        proposals_b=proposals_b,
        compression=compression,
    )
    if result is None:
        return None
    f = finding(
        "D1",
        "copy-move" if same_image else "image-reuse",
        "info" if not same_image and a.work_id == b.work_id else "review",
        [a.work_id] if same_image else [a.work_id, b.work_id],
        [a.artifact_id] if same_image else [a.artifact_id, b.artifact_id],
        f"Small regions in {'panel ' + a.id if same_image else 'panels ' + a.id + ' and ' + b.id} have correlated pixel structure and spatial detail; consistent with duplication and warrants review.",
        parameters={
            "method": "component-pixel-corroboration-v2"
            if compression
            else "component-pixel-corroboration-v1",
            **params,
            "texture_support": TEXTURE_PARAMETERS,
        },
        measurements={
            "category": 3 if same_image else 2,
            "source_points": result.source.tolist(),
            "target_points": result.target.tolist(),
            "source_figure_points": coordinates(a, aa.shape, result.source),
            "target_figure_points": coordinates(b, bb.shape, result.target),
            "coordinate_system": "source_points/target_points: normalized unflipped panels; figure_points: original figure pixels",
            "pixel_ncc": result.ncc,
            "residual_ncc": result.residual_ncc,
            "corroboration": result.mode,
            "smoothed_ncc": result.smoothed_ncc,
            "detail_ncc": result.detail_ncc,
            "template_scale": result.scale,
            "flipped_for_match": result.flipped,
            "panel_ids": [a.id, b.id],
        },
        limitations=[
            "This is a bounded search for dark components on light backgrounds, not a general blot classifier.",
            (
                "Experimental component search preserves native pixels up to a 2400-pixel side and searches discrete scales; it trades sensitivity for fewer smooth-envelope matches."
                if compression
                else "Component search uses a 900-pixel side and translation, horizontal reflection and linear brightness; resizing and compression can hide small clones."
            ),
            "Fine residual correlation does not establish intent or biological identity; repeated controls and figure assembly require expert review.",
            "Heuristic texture filtering can exclude legitimate smooth experimental images; absent findings do not establish a clean figure.",
        ],
    )
    return Match(f, overlay(aa, bb, result.source, result.target))


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
    a: Panel,
    b: Panel,
    *,
    min_inliers=14,
    min_ratio=0.55,
    cached_a=None,
    cached_b=None,
    normalized_a=None,
    normalized_b=None,
    flipped_features_b=None,
    raw_a=None,
    raw_b=None,
    proposals_a=None,
    proposals_b=None,
    pixel_raw_a=None,
    pixel_raw_b=None,
    compression=False,
) -> Match | None:
    raw_a = luminance(a.pixels) if raw_a is None else raw_a
    raw_b = luminance(b.pixels) if raw_b is None else raw_b
    aa = gray(a.pixels) if normalized_a is None else normalized_a
    bb = gray(b.pixels) if normalized_b is None else normalized_b
    if min(np.std(aa), np.std(bb)) < 7 or min(*aa.shape, *bb.shape) < 48:
        return None
    ha, ka, da = cached_a or (hashes(aa), *features(aa, raw_a))
    hb, kb, db = cached_b or (hashes(bb), *features(bb, raw_b))
    distance = hash_distance(ha, hb)
    best = None
    for flipped in (False, True):
        target = np.ascontiguousarray(np.fliplr(bb)) if flipped else bb
        k2, d2 = (
            (
                flipped_features_b
                if flipped_features_b is not None
                else features(target, np.fliplr(raw_b))
            )
            if flipped
            else (kb, db)
        )
        matches = good_matches(da, d2)
        # Descriptor retrieval rescues crops that global hashes cannot shortlist.
        if distance > 12 and len(matches) < min_inliers:
            continue
        if len(matches) < min_inliers:
            continue
        src = np.float32([ka[m.queryIdx].pt for m in matches])
        dst = np.float32([k2[m.trainIdx].pt for m in matches])
        # SIFT emits multiple orientations at one location; they are not independent support.
        _, unique = np.unique(np.rint(np.c_[src, dst]), axis=0, return_index=True)
        src, dst = src[np.sort(unique)], dst[np.sort(unique)]
        if len(src) < min_inliers:
            continue
        cv2.setRNGSeed(0)
        matrix, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        if matrix is None or mask is None or not np.isfinite(matrix).all():
            continue
        inliers = mask.ravel().astype(bool)
        count = int(inliers.sum())
        ratio = count / len(src)
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
        return pixel_finding(
            a,
            b,
            compression=compression,
            raw_a=pixel_raw_a,
            raw_b=pixel_raw_b,
            proposals_a=proposals_a,
            proposals_b=proposals_b,
        )
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
            "content_gate": "distributed fine texture v1",
            "texture_support": TEXTURE_PARAMETERS,
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
            "source_points": src.tolist(),
            "target_points": (dst * [-1, 1] + [bb.shape[1] - 1, 0] if flipped else dst).tolist(),
            "source_figure_points": coordinates(a, aa.shape, src),
            "target_figure_points": coordinates(
                b, bb.shape, dst * [-1, 1] + [bb.shape[1] - 1, 0] if flipped else dst
            ),
            "coordinate_system": "source_points/target_points: normalized unflipped panels; homography: normalized optionally flipped target; figure_points: original figure pixels",
        },
        limitations=[
            "Bik-style category describes geometry, not intent; category 2 includes benign resizing.",
            "Category 3 local differences may also reflect annotations, compression or resampling; examine original images.",
            "Check attribution, shared controls, review republication, versions and corrections.",
            "Matching regions can be small; captions and original figures require inspection.",
            "Heuristic texture filtering can exclude smooth or diagrammatic experimental content; absence is not evidence of a clean figure.",
        ],
    )
    return Match(f, overlay(aa, target, src, dst))


def copy_move(
    panel: Panel,
    *,
    min_matches=10,
    cached=None,
    raw=None,
    proposals=None,
    pixel_raw=None,
    compression=False,
) -> Match | None:
    raw = luminance(panel.pixels) if raw is None else raw

    def fallback():
        return pixel_finding(
            panel,
            panel,
            same_image=True,
            compression=compression,
            raw_a=pixel_raw,
            raw_b=pixel_raw,
            proposals_a=proposals,
            proposals_b=proposals,
        )

    if cached is None:
        a = gray(panel.pixels)
        kp, des = features(a, raw)
    else:
        a, kp, des = cached
    if des is None or len(des) < 20:
        return fallback()
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
        return fallback()
    pairs = list(max(clusters.values(), key=len).values())
    if len(pairs) < min_matches:
        return fallback()
    src, dst = np.float32([p for p, _ in pairs]), np.float32([q for _, q in pairs])
    area = cv2.contourArea(cv2.convexHull(src))
    if area < 0.005 * a.size:
        return fallback()
    f = finding(
        "D1",
        "copy-move",
        "strong",
        [panel.work_id],
        [panel.artifact_id],
        f"Panel {panel.id} contains repeated spatially separated regions consistent with duplication.",
        parameters={
            "min_matches": min_matches,
            "displacement_bin_px": 5,
            "ratio": 0.65,
            "content_gate": "distributed fine texture v1",
            "texture_support": TEXTURE_PARAMETERS,
        },
        measurements={
            "category": 3,
            "matches": len(pairs),
            "source_points": src.tolist(),
            "target_points": dst.tolist(),
            "panel_id": panel.id,
            "source_figure_points": coordinates(panel, a.shape, src),
            "target_figure_points": coordinates(panel, a.shape, dst),
            "coordinate_system": "source_points/target_points: normalized unflipped panel; figure_points: original figure pixels",
        },
        limitations=[
            "Natural repeating structure and assembly of figure panels can produce this signal.",
            "Translation-based copy-move only; rotated, blended or very small clones can be missed.",
            "Heuristic texture filtering can exclude smooth experimental content; absent findings do not establish a clean figure.",
        ],
    )
    return Match(f, overlay(a, a, src, dst))


def detect(panels: list[Panel], *, compression=False) -> list[Match]:
    results = []
    cache = {}
    normalized = {}
    flipped = {}
    raw = {}
    pixel_raw = {}
    proposals = {}
    for p in panels:
        a = gray(p.pixels)
        raw[p.id] = luminance(p.pixels)
        pixel_raw[p.id] = luminance(p.pixels, region_parameters(compression)["max_image_side"])
        proposals[p.id] = regions(pixel_raw[p.id])
        cache[p.id] = (hashes(a), *features(a, raw[p.id]))
        normalized[p.id] = a
        flipped[p.id] = features(np.ascontiguousarray(np.fliplr(a)), np.fliplr(raw[p.id]))
        m = copy_move(
            p,
            cached=(a, *cache[p.id][1:]),
            raw=raw[p.id],
            proposals=proposals[p.id],
            pixel_raw=pixel_raw[p.id],
            compression=compression,
        )
        if m:
            results.append(m)
    for a, b in combinations(panels, 2):
        if a.artifact_id == b.artifact_id:
            continue
        m = compare(
            a,
            b,
            cached_a=cache[a.id],
            cached_b=cache[b.id],
            normalized_a=normalized[a.id],
            normalized_b=normalized[b.id],
            flipped_features_b=flipped[b.id],
            raw_a=raw[a.id],
            raw_b=raw[b.id],
            compression=compression,
            pixel_raw_a=pixel_raw[a.id],
            pixel_raw_b=pixel_raw[b.id],
            proposals_a=proposals[a.id],
            proposals_b=proposals[b.id],
        )
        if m:
            results.append(m)
    return results
