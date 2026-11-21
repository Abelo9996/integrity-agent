"""Deterministic texture support and localized pixel corroboration, without OCR.

These heuristics describe pixels, not semantics: smooth or diagrammatic experimental
images can be excluded. A failed content gate is not evidence that a figure is benign.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

TEXTURE_PARAMETERS = {
    "min_patch_std": 5,
    "residual_blur_sigma": 0.8,
    "min_median_absolute_residual": 0.6,
    "max_extreme_fraction": 0.5,
    "extreme_bounds": [4, 251],
    "max_single_intensity_fraction": 0.35,
    "min_gradient_eigenvalue_ratio": 0.07,
    "keypoint_patch_radius": 12,
}

REGION_PARAMETERS = {
    "max_components": 64,
    "component_contrast": 18,
    "min_component_area": 20,
    "min_patch_pixels": 128,
    "min_patch_ncc": 0.97,
    "min_residual_ncc": 0.75,
    "descriptor_candidates": 16,
    "descriptor_ncc": 0.9,
    "scales": [0.8, 1.0, 1.25],
    "max_image_side": 2400,
    "structure_removed_rank": 2,
    "structure_min_ncc": 0.75,
    "structure_min_energy_fraction": 0.005,
    "compression_blur_sigmas": [1.2, 2.5],
    "compression_gradient_quantile": 0.6,
    "compression_border": 2,
    "compression_pixel_ncc": 0.98,
    "compression_smoothed_ncc": 0.995,
    "compression_detail_ncc": 0.75,
    "compression_min_detail_std": 0.25,
    "compression_min_support_pixels": 96,
    "transforms": ["translation", "horizontal reflection", "linear brightness", "discrete scale"],
}


def region_parameters(compression=False):
    if compression:
        return REGION_PARAMETERS.copy()
    keys = (
        "max_components",
        "component_contrast",
        "min_component_area",
        "min_patch_pixels",
        "min_patch_ncc",
        "min_residual_ncc",
        "descriptor_candidates",
        "descriptor_ncc",
    )
    return {
        **{k: REGION_PARAMETERS[k] for k in keys},
        "max_image_side": 900,
        "transforms": ["translation", "horizontal reflection", "linear brightness"],
    }


def luminance(pixels, max_side=900):
    a = np.asarray(pixels, dtype=np.uint8)
    if a.ndim == 3:
        a = cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2GRAY)
    if max(a.shape) > max_side:
        scale = max_side / max(a.shape)
        a = cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return a


def residual(a):
    value = a.astype(np.float32)
    return value - cv2.GaussianBlur(value, (0, 0), TEXTURE_PARAMETERS["residual_blur_sigma"])


def texture_supported(patch):
    if (
        min(patch.shape) < 6
        or patch.size < 64
        or np.std(patch) < TEXTURE_PARAMETERS["min_patch_std"]
    ):
        return False
    # Flat backgrounds, antialiased lettering and rules usually leave most pixels
    # unchanged by this blur. Require distributed fine variation, not only edges.
    if (
        float(np.median(np.abs(residual(patch))))
        < TEXTURE_PARAMETERS["min_median_absolute_residual"]
    ):
        return False
    low, high = TEXTURE_PARAMETERS["extreme_bounds"]
    if (
        float(((patch <= low) | (patch >= high)).mean())
        > TEXTURE_PARAMETERS["max_extreme_fraction"]
    ):
        return False
    # Also reject gray/colored flat backgrounds; do not assume text is black on white.
    if (
        np.bincount(patch.ravel(), minlength=256).max() / patch.size
        > TEXTURE_PARAMETERS["max_single_intensity_fraction"]
    ):
        return False
    # Reject effectively one-dimensional stripes/hatching.
    gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1)
    covariance = np.array(
        [[np.mean(gx * gx), np.mean(gx * gy)], [np.mean(gx * gy), np.mean(gy * gy)]]
    )
    values = np.linalg.eigvalsh(covariance)
    return bool(
        values[0] > TEXTURE_PARAMETERS["min_gradient_eigenvalue_ratio"] * max(float(values[1]), 1)
    )


def supported_features(raw, keypoints, descriptors):
    if descriptors is None:
        return keypoints, descriptors
    selected = []
    radius = TEXTURE_PARAMETERS["keypoint_patch_radius"]
    for i, point in enumerate(keypoints):
        x, y = np.rint(point.pt).astype(int)
        patch = raw[max(0, y - radius) : y + radius + 1, max(0, x - radius) : x + radius + 1]
        if texture_supported(patch):
            selected.append(i)
    if not selected:
        return [], None
    return [keypoints[i] for i in selected], descriptors[selected]


@dataclass
class Region:
    box: tuple[int, int, int, int]
    pixels: np.ndarray
    descriptor: np.ndarray


def descriptor(pixels):
    a = cv2.resize(pixels, (24, 16), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    a -= a.mean()
    return a / max(float(np.linalg.norm(a)), 1e-6)


def regions(raw):
    """Bounded dark-component proposals for bands on light backgrounds."""
    smooth = cv2.GaussianBlur(raw, (0, 0), 1)
    background = cv2.morphologyEx(
        smooth, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 25))
    )
    mask = (cv2.subtract(background, smooth) >= REGION_PARAMETERS["component_contrast"]).astype(
        np.uint8
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    proposals = []
    for x, y, w, h, area in sorted(stats[1:], key=lambda row: (-row[4], row[1], row[0])):
        if not (20 <= area <= 6000 and 8 <= w <= 160 and 3 <= h <= 100):
            continue
        x0, y0 = max(0, int(x) - 3), max(0, int(y) - 3)
        x1, y1 = min(raw.shape[1], int(x + w) + 3), min(raw.shape[0], int(y + h) + 3)
        patch = raw[y0:y1, x0:x1]
        if patch.size < REGION_PARAMETERS["min_patch_pixels"] or not texture_supported(patch):
            continue
        proposals.append(Region((x0, y0, x1 - x0, y1 - y0), patch, descriptor(patch)))
        if len(proposals) == REGION_PARAMETERS["max_components"]:
            break
    return proposals


def correlation(a, b):
    x, y = a.astype(np.float32).ravel(), b.astype(np.float32).ravel()
    x, y = x - x.mean(), y - y.mean()
    return float(
        np.clip(np.dot(x, y) / max(float(np.linalg.norm(x) * np.linalg.norm(y)), 1e-6), -1, 1)
    )


@dataclass
class PixelMatch:
    source: np.ndarray
    target: np.ndarray
    ncc: float
    residual_ncc: float
    flipped: bool
    scale: float = 1.0
    mode: str = "fine-residual"
    smoothed_ncc: float | None = None
    detail_ncc: float | None = None


def structure_support(a, b):
    """Require shared detail beyond a low-rank smooth envelope."""

    def detail(patch):
        value = patch.astype(np.float32)
        value -= value.mean()
        u, singular, v = np.linalg.svd(value, full_matrices=False)
        rank = REGION_PARAMETERS["structure_removed_rank"]
        rest = value - (u[:, :rank] * singular[:rank]) @ v[:rank]
        energy = float(np.sum(rest**2) / max(float(np.sum(value**2)), 1e-6))
        return rest, energy

    da, ea = detail(a)
    db, eb = detail(b)
    return (
        min(ea, eb) >= REGION_PARAMETERS["structure_min_energy_fraction"]
        and correlation(da, db) >= REGION_PARAMETERS["structure_min_ncc"]
    )


def compression_support(a, b):
    """Corroborate surviving spatial detail away from strong shape edges.

    Matching a smooth silhouette alone is insufficient. Compare band-pass detail
    on common low-gradient pixels, where JPEG's high-frequency loss matters less.
    """
    a, b = a.astype(np.float32), b.astype(np.float32)
    small, large = REGION_PARAMETERS["compression_blur_sigmas"]
    smooth_a = cv2.GaussianBlur(a, (0, 0), small)
    smooth_b = cv2.GaussianBlur(b, (0, 0), small)
    smooth_score = correlation(smooth_a, smooth_b)
    if smooth_score < REGION_PARAMETERS["compression_smoothed_ncc"]:
        return None

    def gradient(image):
        return cv2.magnitude(cv2.Sobel(image, cv2.CV_32F, 1, 0), cv2.Sobel(image, cv2.CV_32F, 0, 1))

    ga, gb = gradient(smooth_a), gradient(smooth_b)
    q = REGION_PARAMETERS["compression_gradient_quantile"]
    mask = (ga <= np.quantile(ga, q)) & (gb <= np.quantile(gb, q))
    border = REGION_PARAMETERS["compression_border"]
    mask[:border] = False
    mask[-border:] = False
    mask[:, :border] = False
    mask[:, -border:] = False
    if mask.sum() < REGION_PARAMETERS["compression_min_support_pixels"]:
        return None
    da = smooth_a - cv2.GaussianBlur(a, (0, 0), large)
    db = smooth_b - cv2.GaussianBlur(b, (0, 0), large)
    if min(np.std(da[mask]), np.std(db[mask])) < REGION_PARAMETERS["compression_min_detail_std"]:
        return None
    detail_score = correlation(da[mask], db[mask])
    if detail_score < REGION_PARAMETERS["compression_detail_ncc"]:
        return None
    return smooth_score, detail_score


def pixel_match(a, b, *, same_image=False, proposals_a=None, proposals_b=None, compression=False):
    first = regions(a) if proposals_a is None else proposals_a
    second = (first if same_image else regions(b)) if proposals_b is None else proposals_b
    if not first or not second:
        return None
    descriptors = np.stack([r.descriptor for r in second])
    best = None
    for source in first:
        x, y, original_w, original_h = source.box
        for flipped in (False, True):
            original = np.ascontiguousarray(np.fliplr(source.pixels)) if flipped else source.pixels
            scores = descriptors @ descriptor(original)
            indices = np.argsort(-scores, kind="stable")[
                : REGION_PARAMETERS["descriptor_candidates"] + int(same_image)
            ]
            for scale in REGION_PARAMETERS["scales"] if compression else [1.0]:
                patch = (
                    cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                    if scale != 1
                    else original
                )
                h, w = patch.shape
                for index in indices:
                    if scores[index] < REGION_PARAMETERS["descriptor_ncc"]:
                        continue
                    target = second[index]
                    tx, ty, tw, th = target.box
                    if same_image and not (
                        x + original_w <= tx or tx + tw <= x or y + original_h <= ty or ty + th <= y
                    ):
                        continue
                    if not (0.65 < tw / w < 1.55 and 0.65 < th / h < 1.55):
                        continue
                    x0, y0 = max(0, tx - 8), max(0, ty - 8)
                    x1, y1 = min(b.shape[1], tx + tw + 8), min(b.shape[0], ty + th + 8)
                    window = b[y0:y1, x0:x1]
                    if window.shape[0] < h or window.shape[1] < w:
                        continue
                    scores_map = cv2.matchTemplate(window, patch, cv2.TM_CCOEFF_NORMED)
                    _, score, _, position = cv2.minMaxLoc(scores_map)
                    if score < REGION_PARAMETERS["min_patch_ncc"]:
                        continue
                    qx, qy = x0 + position[0], y0 + position[1]
                    if same_image and not (
                        x + original_w <= qx or qx + w <= x or y + original_h <= qy or qy + h <= y
                    ):
                        continue
                    matched = b[qy : qy + h, qx : qx + w]
                    if compression and not structure_support(patch, matched):
                        continue
                    noise_score = correlation(residual(patch), residual(matched))
                    support = None
                    if noise_score < REGION_PARAMETERS["min_residual_ncc"]:
                        if not compression or score < REGION_PARAMETERS["compression_pixel_ncc"]:
                            continue
                        support = compression_support(patch, matched)
                        if support is None:
                            continue
                    quality = noise_score if support is None else support[1]
                    old_quality = (
                        (best.residual_ncc if best.mode == "fine-residual" else best.detail_ncc)
                        if best
                        else -1
                    )
                    if quality <= old_quality:
                        continue
                    # Corners refer to actual supported patches, not whole-figure boxes.
                    src = np.float32(
                        [
                            [x, y],
                            [x + original_w - 1, y],
                            [x + original_w - 1, y + original_h - 1],
                            [x, y + original_h - 1],
                        ]
                    )
                    dst = np.float32(
                        [[qx, qy], [qx + w - 1, qy], [qx + w - 1, qy + h - 1], [qx, qy + h - 1]]
                    )
                    if flipped:
                        dst = dst[[1, 0, 3, 2]]
                    best = PixelMatch(
                        src,
                        dst,
                        float(score),
                        noise_score,
                        flipped,
                        scale,
                        "compression-detail" if support else "fine-residual",
                        *(support or (None, None)),
                    )
    return best
