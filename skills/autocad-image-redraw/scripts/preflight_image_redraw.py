#!/usr/bin/env python
"""Preflight a raster source before image-to-CAD reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

PROFILES = {"strict-dimensioned", "general", "hybrid", "visual-trace", "geometry-only"}
UNITS = {"unitless", "mm", "cm", "m", "in", "ft", "unknown"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_anchors(path: Path | None) -> dict:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Anchors JSON must be an object.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight a raster drawing reference.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=sorted(PROFILES), default="general")
    parser.add_argument("--units", choices=sorted(UNITS), default="unknown")
    parser.add_argument("--anchors-json", help="Optional JSON containing an anchors array or calibration records.")
    parser.add_argument("--min-short-edge", type=int, default=700)
    args = parser.parse_args()

    source = Path(args.image).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    warnings: list[str] = []
    blockers: list[str] = []
    checks: list[dict] = []

    if not source.is_file():
        report = {"tool": "preflight_image_redraw/1.0", "status": "fail", "blockers": [f"Image not found: {source}"]}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 3

    try:
        with Image.open(source) as raw:
            exif_orientation = raw.getexif().get(274)
            normalized = ImageOps.exif_transpose(raw).convert("RGB")
            fmt = raw.format
            original_size = list(raw.size)
        rgb = np.asarray(normalized)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    except Exception as exc:
        report = {"tool": "preflight_image_redraw/1.0", "status": "fail", "blockers": [f"Unreadable image: {exc}"]}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 3

    height, width = gray.shape
    contrast = float(gray.std())
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    dark_fraction = float(np.mean(gray < 64))
    light_fraction = float(np.mean(gray > 245))
    anchors = load_anchors(Path(args.anchors_json).expanduser().resolve() if args.anchors_json else None)
    anchor_records = anchors.get("anchors", anchors.get("calibration", []))
    anchor_count = len(anchor_records) if isinstance(anchor_records, list) else 0

    checks.append({"name": "readable", "passed": True})
    checks.append({"name": "short_edge", "passed": min(width, height) >= args.min_short_edge, "value": min(width, height)})
    if min(width, height) < args.min_short_edge:
        warnings.append(f"Short image edge is {min(width, height)} px; small features or text may be unreliable.")
    if contrast < 18:
        warnings.append(f"Low global contrast ({contrast:.1f}); line separation may be unreliable.")
    if blur_variance < 45:
        warnings.append(f"Low Laplacian variance ({blur_variance:.1f}); source may be blurred.")
    if exif_orientation not in (None, 1):
        warnings.append(f"EXIF orientation {exif_orientation} was normalized for analysis.")
    if light_fraction < 0.15 and dark_fraction < 0.02:
        warnings.append("The source is not paper-like; verify thresholding and edge settings manually.")

    physical_units = args.units not in {"unknown", "unitless"}
    if args.mode == "strict-dimensioned":
        if not physical_units:
            blockers.append("strict-dimensioned mode requires known physical units.")
        if anchor_count == 0:
            blockers.append("strict-dimensioned mode requires at least one documented scale/calibration anchor.")
    elif args.mode == "hybrid" and (not physical_units or anchor_count == 0):
        warnings.append("Hybrid mode lacks physical units or calibration anchors; dimensioned regions need review.")

    if blockers:
        status = "blocked"
        exit_code = 3
    elif warnings:
        status = "pass_with_warnings"
        exit_code = 0
    else:
        status = "pass"
        exit_code = 0

    report = {
        "tool": "preflight_image_redraw/1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [{"path": str(source), "sha256": sha256(source)}],
        "profile": args.mode,
        "status": status,
        "checks": checks,
        "metrics": {
            "format": fmt,
            "original_pixel_size": original_size,
            "normalized_pixel_size": [width, height],
            "exif_orientation": exif_orientation,
            "grayscale_mean": float(gray.mean()),
            "grayscale_stddev": contrast,
            "laplacian_variance": blur_variance,
            "dark_fraction": dark_fraction,
            "light_fraction": light_fraction,
            "anchor_count": anchor_count,
            "declared_units": args.units,
        },
        "warnings": warnings,
        "blockers": blockers,
        "next_actions": ["Review crop, perspective, occlusion, and dimension endpoint attachment manually."],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(output), "status": status, "warnings": len(warnings), "blockers": len(blockers)}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
