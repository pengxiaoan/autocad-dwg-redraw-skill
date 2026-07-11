#!/usr/bin/env python
"""Register a CAD preview to its source image and compare linework."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def read_points(data: dict, key: str) -> np.ndarray:
    points = np.asarray(data.get(key, []), dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 4:
        raise ValueError(f"{key} must contain at least four [x, y] points.")
    return points


def register_views(cad: np.ndarray, anchors: dict, output_size: tuple[int, int]) -> tuple[np.ndarray, int, int]:
    """Register one global view or several independently scaled/perspective views."""
    width, height = output_size
    view_specs = anchors.get("views")
    if not isinstance(view_specs, list) or not view_specs:
        view_specs = [anchors]
    composite = np.full((height, width, 3), 255, dtype=np.uint8)
    coverage = np.zeros((height, width), dtype=np.uint8)
    total_inliers = 0
    for index, view in enumerate(view_specs, 1):
        source_points = read_points(view, "source_points")
        cad_points = read_points(view, "cad_points")
        if len(source_points) != len(cad_points):
            raise ValueError(f"View #{index} has mismatched source_points and cad_points.")
        homography, inliers = cv2.findHomography(cad_points, source_points, cv2.RANSAC, 4.0)
        if homography is None:
            raise ValueError(f"Cannot compute homography for view #{index}.")
        warped = cv2.warpPerspective(cad, homography, (width, height), borderValue=(255, 255, 255))
        roi = view.get("source_roi", [0, 0, width, height])
        if len(roi) != 4:
            raise ValueError(f"View #{index} source_roi must be [left, top, right, bottom].")
        left, top, right, bottom = [int(round(v)) for v in roi]
        left, top = max(0, left), max(0, top)
        right, bottom = min(width, right), min(height, bottom)
        if right <= left or bottom <= top:
            raise ValueError(f"View #{index} source_roi is empty after clipping.")
        composite[top:bottom, left:right] = warped[top:bottom, left:right]
        coverage[top:bottom, left:right] = 255
        total_inliers += int(inliers.sum()) if inliers is not None else 0
    composite[coverage == 0] = 255
    return composite, len(view_specs), total_inliers


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare registered source and CAD-preview edges.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--cad-preview", required=True)
    parser.add_argument("--anchors", required=True, help="JSON with matching source_points and cad_points.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--thresholds", default="3,5,10", help="Pixel edge-distance thresholds.")
    args = parser.parse_args()

    source_path = Path(args.source).expanduser().resolve()
    cad_path = Path(args.cad_preview).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    cad = cv2.imread(str(cad_path), cv2.IMREAD_COLOR)
    if source is None or cad is None:
        raise SystemExit("Cannot read source image or CAD preview.")
    anchors = json.loads(Path(args.anchors).read_text(encoding="utf-8"))
    height, width = source.shape[:2]
    try:
        warped, view_count, inlier_count = register_views(cad, anchors, (width, height))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    source_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    cad_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    source_edges = cv2.Canny(source_gray, 60, 180)
    cad_edges = cv2.Canny(cad_gray, 60, 180)
    distance_to_source = cv2.distanceTransform(255 - source_edges, cv2.DIST_L2, 3)
    distance_to_cad = cv2.distanceTransform(255 - cad_edges, cv2.DIST_L2, 3)
    cad_distances = distance_to_source[cad_edges > 0]
    source_distances = distance_to_cad[source_edges > 0]
    thresholds = [float(v) for v in args.thresholds.split(",") if v.strip()]

    metrics = {
        "tool": "compare_redraw/1.0", "status": "pass", "metric_scope": "visual_registration_only",
        "view_count": view_count, "homography_inliers": inlier_count,
        "source_edge_pixels": int(np.count_nonzero(source_edges)), "cad_edge_pixels": int(np.count_nonzero(cad_edges)),
        "cad_to_source_median_px": float(np.median(cad_distances)) if cad_distances.size else None,
        "cad_to_source_p95_px": float(np.percentile(cad_distances, 95)) if cad_distances.size else None,
        "source_to_cad_median_px": float(np.median(source_distances)) if source_distances.size else None,
        "source_to_cad_p95_px": float(np.percentile(source_distances, 95)) if source_distances.size else None,
        "cad_edge_within_threshold": {str(v): float(np.mean(cad_distances <= v)) if cad_distances.size else 0.0 for v in thresholds},
        "source_edge_coverage": {str(v): float(np.mean(source_distances <= v)) if source_distances.size else 0.0 for v in thresholds},
        "warning": "These metrics assess registered visual linework, not physical dimensions or units."
    }
    overlay = cv2.addWeighted(source, 0.60, warped, 0.40, 0)
    difference = np.full_like(source, 255)
    difference[source_edges > 0] = (0, 0, 255)
    difference[cad_edges > 0] = (255, 0, 0)
    both = (source_edges > 0) & (cad_edges > 0)
    difference[both] = (0, 160, 0)
    cad_resized = cv2.resize(cad, (width, height), interpolation=cv2.INTER_AREA)
    side_by_side = np.hstack([source, cad_resized])
    cv2.imwrite(str(output / "registered-cad.png"), warped)
    cv2.imwrite(str(output / "overlay.png"), overlay)
    cv2.imwrite(str(output / "edge-difference.png"), difference)
    cv2.imwrite(str(output / "side-by-side.png"), side_by_side)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
