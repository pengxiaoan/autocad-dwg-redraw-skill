#!/usr/bin/env python
"""Open-source raster CAD screenshot to DXF prototype.

This is a visual vectorization pipeline, not a semantic mechanical drawing parser.
It turns bright/dark linework from a raster image into DXF entities using OpenCV
and ezdxf. Text and dimensions are preserved as traced geometry unless a later
OCR/AI stage converts them into real CAD annotations.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import ezdxf
import numpy as np


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return image


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, data = cv2.imencode(ext, image)
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    data.tofile(str(path))


def make_linework_mask(image: np.ndarray, threshold: int, polarity: str) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if polarity == "auto":
        polarity = "dark" if float(gray.mean()) > 128 else "light"
    if polarity == "dark":
        mask = cv2.inRange(gray, 0, threshold)
    else:
        mask = cv2.inRange(gray, threshold, 255)
    return mask


def crop_sheet(image: np.ndarray, mask: np.ndarray, margin: int, min_area_ratio: float) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = mask.shape[:2]
    best = None
    best_area = 0
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        if area < w * h * min_area_ratio:
            continue
        if area > best_area:
            best = (x, y, cw, ch)
            best_area = area
    if best is None:
        return image, mask, (0, 0, w, h)
    x, y, cw, ch = best
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(w, x + cw + margin)
    y2 = min(h, y + ch + margin)
    return image[y1:y2, x1:x2].copy(), mask[y1:y2, x1:x2].copy(), (x1, y1, x2 - x1, y2 - y1)


def preprocess_mask(mask: np.ndarray, close_iters: int, dilate_iters: int) -> np.ndarray:
    kernel = np.ones((3, 3), np.uint8)
    out = mask.copy()
    if close_iters > 0:
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, kernel, iterations=close_iters)
    if dilate_iters > 0:
        out = cv2.dilate(out, kernel, iterations=dilate_iters)
    return out


def length(line: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = line
    return math.hypot(x2 - x1, y2 - y1)


def snap_line(line: tuple[int, int, int, int], snap_degrees: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = line
    dx = x2 - x1
    dy = y2 - y1
    angle = abs(math.degrees(math.atan2(dy, dx))) % 180
    if min(angle, 180 - angle) <= snap_degrees:
        y = int(round((y1 + y2) / 2))
        return x1, y, x2, y
    if abs(angle - 90) <= snap_degrees:
        x = int(round((x1 + x2) / 2))
        return x, y1, x, y2
    return line


def detect_lines(mask: np.ndarray, min_length: int, max_gap: int, threshold: int, snap_degrees: float) -> list[tuple[int, int, int, int]]:
    raw = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=threshold, minLineLength=min_length, maxLineGap=max_gap)
    if raw is None:
        return []
    seen = set()
    lines: list[tuple[int, int, int, int]] = []
    for item in raw[:, 0, :]:
        line = snap_line(tuple(int(v) for v in item), snap_degrees)
        if length(line) < min_length:
            continue
        key = tuple(round(v / 2) * 2 for v in line)
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
    return lines


def detect_circles(mask: np.ndarray, min_radius: int, max_radius: int, param2: int) -> list[tuple[int, int, int]]:
    blurred = cv2.medianBlur(mask, 5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(12, min_radius * 2),
        param1=80,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None:
        return []
    result = []
    seen = set()
    for x, y, r in np.round(circles[0, :]).astype(int):
        key = (round(x / 3) * 3, round(y / 3) * 3, round(r / 2) * 2)
        if key in seen:
            continue
        seen.add(key)
        result.append((int(x), int(y), int(r)))
    return result


def trace_contours(mask: np.ndarray, min_area: float, min_perimeter: float, epsilon_ratio: float, max_vertices: int) -> list[list[tuple[int, int]]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    traced: list[list[tuple[int, int]]] = []
    for contour in contours:
        area = abs(cv2.contourArea(contour))
        perimeter = cv2.arcLength(contour, True)
        if area < min_area and perimeter < min_perimeter:
            continue
        epsilon = max(0.6, perimeter * epsilon_ratio)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 2 or len(approx) > max_vertices:
            continue
        points = [(int(p[0][0]), int(p[0][1])) for p in approx]
        traced.append(points)
    return traced


def to_cad_point(x: float, y: float, height: int, scale: float) -> tuple[float, float]:
    return float(x) * scale, float(height - y) * scale


def add_layers(doc: ezdxf.EzDxf) -> None:
    layers = {
        "RASTER_LINES": 7,
        "RASTER_CIRCLES": 3,
        "RASTER_CONTOURS": 8,
        "RASTER_BORDER": 2,
    }
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def write_dxf(
    output: Path,
    image_shape: tuple[int, int, int],
    scale: float,
    lines: list[tuple[int, int, int, int]],
    circles: list[tuple[int, int, int]],
    contours: list[list[tuple[int, int]]],
    add_border: bool,
) -> Counter:
    h, w = image_shape[:2]
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    add_layers(doc)
    msp = doc.modelspace()
    counts = Counter()
    if add_border:
        points = [
            to_cad_point(0, 0, h, scale),
            to_cad_point(w, 0, h, scale),
            to_cad_point(w, h, h, scale),
            to_cad_point(0, h, h, scale),
            to_cad_point(0, 0, h, scale),
        ]
        msp.add_lwpolyline(points, dxfattribs={"layer": "RASTER_BORDER"})
        counts["border"] += 1
    for x1, y1, x2, y2 in lines:
        msp.add_line(to_cad_point(x1, y1, h, scale), to_cad_point(x2, y2, h, scale), dxfattribs={"layer": "RASTER_LINES"})
        counts["line"] += 1
    for x, y, r in circles:
        msp.add_circle(to_cad_point(x, y, h, scale), float(r) * scale, dxfattribs={"layer": "RASTER_CIRCLES"})
        counts["circle"] += 1
    for contour in contours:
        if len(contour) < 2:
            continue
        points = [to_cad_point(x, y, h, scale) for x, y in contour]
        if points[0] != points[-1]:
            points.append(points[0])
        msp.add_lwpolyline(points, dxfattribs={"layer": "RASTER_CONTOURS"})
        counts["contour"] += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
    return counts


def convert_dxf_to_dwg(dxf_path: Path, dwg_path: Path, attach_document: str | None = None) -> dict[str, Any]:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise SystemExit("pywin32 is required for DXF-to-DWG conversion through AutoCAD.") from exc
    pythoncom.CoInitialize()
    app = None
    if attach_document:
        try:
            base_doc = win32com.client.GetObject(str(Path(attach_document).resolve()))
            app = base_doc.Application
        except Exception:
            app = None
    if app is None:
        try:
            app = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            app = win32com.client.Dispatch("AutoCAD.Application")
    try:
        app.Visible = True
    except Exception:
        pass
    if dwg_path.exists():
        dwg_path.unlink()
    app.Documents.Open(str(dxf_path))
    time.sleep(0.5)
    doc = app.ActiveDocument
    entity_count = int(doc.ModelSpace.Count)
    doc.SaveAs(str(dwg_path))
    return {"dwg": str(dwg_path), "autocad_document": str(doc.Name), "modelspace_entities": entity_count}


def draw_preview(image: np.ndarray, lines: list[tuple[int, int, int, int]], circles: list[tuple[int, int, int]], contours: list[list[tuple[int, int]]]) -> np.ndarray:
    preview = image.copy()
    for contour in contours:
        pts = np.array(contour, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(preview, [pts], True, (128, 128, 128), 1, cv2.LINE_AA)
    for x1, y1, x2, y2 in lines:
        cv2.line(preview, (x1, y1), (x2, y2), (0, 255, 255), 1, cv2.LINE_AA)
    for x, y, r in circles:
        cv2.circle(preview, (x, y), r, (0, 220, 80), 1, cv2.LINE_AA)
    return preview


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vectorize a CAD screenshot into DXF using OpenCV and ezdxf.")
    parser.add_argument("--image", required=True, help="Input screenshot/image path.")
    parser.add_argument("--output", required=True, help="Output DXF path.")
    parser.add_argument("--dwg-output", help="Optional DWG output path. Requires AutoCAD COM; the vectorization itself remains DXF-based.")
    parser.add_argument("--attach-document", help="Bind AutoCAD COM through a specific readable DWG when using --dwg-output.")
    parser.add_argument("--preview", help="Optional preview PNG path.")
    parser.add_argument("--stats", help="Optional JSON statistics path.")
    parser.add_argument("--polarity", choices=["auto", "light", "dark"], default="auto", help="Linework polarity. light=bright lines, dark=dark lines.")
    parser.add_argument("--threshold", type=int, default=150, help="Binary threshold. For light linework, pixels >= threshold are selected.")
    parser.add_argument("--scale", type=float, default=1.0, help="DXF units per pixel. Default keeps pixel-sized CAD coordinates.")
    parser.add_argument("--no-auto-crop", action="store_true", help="Do not crop to the detected sheet/border area.")
    parser.add_argument("--crop-margin", type=int, default=4, help="Pixel margin around detected sheet crop.")
    parser.add_argument("--crop-min-area-ratio", type=float, default=0.20, help="Minimum contour bounding-box area ratio for sheet crop.")
    parser.add_argument("--close-iters", type=int, default=1, help="Morphological close iterations.")
    parser.add_argument("--dilate-iters", type=int, default=0, help="Morphological dilation iterations.")
    parser.add_argument("--min-line-length", type=int, default=22, help="Minimum Hough line length in pixels.")
    parser.add_argument("--max-line-gap", type=int, default=5, help="Maximum Hough line gap in pixels.")
    parser.add_argument("--hough-threshold", type=int, default=45, help="Hough line accumulator threshold.")
    parser.add_argument("--snap-degrees", type=float, default=1.5, help="Snap near-horizontal/vertical lines by this angle tolerance.")
    parser.add_argument("--circles", action="store_true", help="Enable Hough circle detection.")
    parser.add_argument("--min-radius", type=int, default=5, help="Minimum circle radius in pixels.")
    parser.add_argument("--max-radius", type=int, default=90, help="Maximum circle radius in pixels.")
    parser.add_argument("--circle-param2", type=int, default=18, help="Hough circle detection threshold.")
    parser.add_argument("--no-contours", action="store_true", help="Disable contour tracing.")
    parser.add_argument("--min-contour-area", type=float, default=6.0, help="Minimum contour area.")
    parser.add_argument("--min-contour-perimeter", type=float, default=10.0, help="Minimum contour perimeter.")
    parser.add_argument("--epsilon-ratio", type=float, default=0.003, help="Contour approximation epsilon ratio.")
    parser.add_argument("--max-contour-vertices", type=int, default=180, help="Skip contour polylines with too many vertices.")
    parser.add_argument("--no-border", action="store_true", help="Do not add output crop border.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    image_path = Path(args.image).resolve()
    output = Path(args.output).resolve()
    image = load_image(image_path)
    mask = make_linework_mask(image, args.threshold, args.polarity)
    crop = (0, 0, image.shape[1], image.shape[0])
    if not args.no_auto_crop:
        image, mask, crop = crop_sheet(image, mask, args.crop_margin, args.crop_min_area_ratio)
    mask = preprocess_mask(mask, args.close_iters, args.dilate_iters)

    lines = detect_lines(mask, args.min_line_length, args.max_line_gap, args.hough_threshold, args.snap_degrees)
    circles = detect_circles(mask, args.min_radius, args.max_radius, args.circle_param2) if args.circles else []
    contours = [] if args.no_contours else trace_contours(mask, args.min_contour_area, args.min_contour_perimeter, args.epsilon_ratio, args.max_contour_vertices)
    counts = write_dxf(output, image.shape, args.scale, lines, circles, contours, not args.no_border)
    dwg_result = None
    if args.dwg_output:
        dwg_result = convert_dxf_to_dwg(output, Path(args.dwg_output).resolve(), args.attach_document)

    preview_path = None
    if args.preview:
        preview_path = Path(args.preview).resolve()
        save_image(preview_path, draw_preview(image, lines, circles, contours))

    stats: dict[str, Any] = {
        "input": str(image_path),
        "output": str(output),
        "dwg_output": dwg_result,
        "preview": str(preview_path) if preview_path else None,
        "source_size": [int(v) for v in load_image(image_path).shape[:2][::-1]],
        "crop": [int(v) for v in crop],
        "crop_size": [int(image.shape[1]), int(image.shape[0])],
        "counts": counts,
        "line_count": len(lines),
        "circle_count": len(circles),
        "contour_count": len(contours),
    }
    if args.stats:
        stats_path = Path(args.stats).resolve()
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
