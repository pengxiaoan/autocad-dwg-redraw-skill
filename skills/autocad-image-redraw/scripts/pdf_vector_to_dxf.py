#!/usr/bin/env python
"""Convert vector PDF drawing paths to DXF, with optional AutoCAD DWG save."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import ezdxf
import fitz


def is_white(color) -> bool:
    if color is None:
        return False
    return all(float(c) >= 0.95 for c in color[:3])


def cad_point(point, page_height: float, scale: float) -> tuple[float, float]:
    return float(point.x) * scale, (page_height - float(point.y)) * scale


def rect_points(rect, page_height: float, scale: float) -> list[tuple[float, float]]:
    corners = [
        fitz.Point(rect.x0, rect.y0),
        fitz.Point(rect.x1, rect.y0),
        fitz.Point(rect.x1, rect.y1),
        fitz.Point(rect.x0, rect.y1),
        fitz.Point(rect.x0, rect.y0),
    ]
    return [cad_point(p, page_height, scale) for p in corners]


def cubic_point(p0, p1, p2, p3, t: float):
    inv = 1 - t
    x = inv**3 * p0.x + 3 * inv**2 * t * p1.x + 3 * inv * t**2 * p2.x + t**3 * p3.x
    y = inv**3 * p0.y + 3 * inv**2 * t * p1.y + 3 * inv * t**2 * p2.y + t**3 * p3.y
    return fitz.Point(x, y)


def cubic_segments(p0, p1, p2, p3, page_height: float, scale: float, segments: int) -> list[tuple[float, float]]:
    return [cad_point(cubic_point(p0, p1, p2, p3, i / segments), page_height, scale) for i in range(segments + 1)]


def add_line(msp, start, end, layer: str) -> None:
    if start == end:
        return
    msp.add_line(start, end, dxfattribs={"layer": layer})


def add_polyline(msp, points: list[tuple[float, float]], layer: str, close: bool = False) -> None:
    if len(points) < 2:
        return
    cleaned = [points[0]]
    for point in points[1:]:
        if point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) < 2:
        return
    if close and cleaned[0] != cleaned[-1]:
        cleaned.append(cleaned[0])
    msp.add_lwpolyline(cleaned, dxfattribs={"layer": layer})


def setup_doc() -> ezdxf.EzDxf:
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name, color in {
        "PDF_STROKE": 7,
        "PDF_FILL_OUTLINE": 8,
        "PDF_RECT": 2,
    }.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    return doc


def convert_page(page, output: Path, scale: float, bezier_segments: int, include_fills: bool, include_white: bool) -> dict[str, Any]:
    doc = setup_doc()
    msp = doc.modelspace()
    counts = Counter()
    page_height = float(page.rect.height)

    for drawing in page.get_drawings():
        drawing_type = drawing.get("type")
        fill = drawing.get("fill")
        stroke = drawing.get("color")
        is_fill = drawing_type == "f"
        if is_fill and not include_fills:
            continue
        if is_fill and is_white(fill) and not include_white:
            continue
        layer = "PDF_FILL_OUTLINE" if is_fill else "PDF_STROKE"
        path_points: list[tuple[float, float]] = []
        first_point: tuple[float, float] | None = None
        current_point: tuple[float, float] | None = None

        for item in drawing.get("items", []):
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
                start = cad_point(p1, page_height, scale)
                end = cad_point(p2, page_height, scale)
                if is_fill:
                    if not path_points:
                        first_point = start
                        path_points.append(start)
                    path_points.append(end)
                    current_point = end
                else:
                    add_line(msp, start, end, layer)
                    counts["line"] += 1
            elif op == "c":
                p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
                points = cubic_segments(p0, p1, p2, p3, page_height, scale, bezier_segments)
                if is_fill:
                    if not path_points:
                        first_point = points[0]
                        path_points.extend(points)
                    else:
                        path_points.extend(points[1:])
                    current_point = points[-1]
                else:
                    add_polyline(msp, points, layer)
                    counts["curve_polyline"] += 1
            elif op == "re":
                rect = item[1]
                points = rect_points(rect, page_height, scale)
                add_polyline(msp, points, "PDF_RECT" if not is_fill else layer, close=False)
                counts["rectangle"] += 1

        if is_fill and path_points:
            close = bool(drawing.get("closePath")) or (first_point is not None and current_point == first_point)
            add_polyline(msp, path_points, layer, close=close)
            counts["filled_outline"] += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output)
    return {
        "output": str(output),
        "page_size": [float(page.rect.width), float(page.rect.height)],
        "counts": counts,
        "entity_total": sum(counts.values()),
    }


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert vector PDF paths to DXF and optionally DWG.")
    parser.add_argument("--pdf", required=True, help="Input vector PDF path.")
    parser.add_argument("--output", required=True, help="Output DXF path.")
    parser.add_argument("--dwg-output", help="Optional DWG output path. Requires AutoCAD COM.")
    parser.add_argument("--attach-document", help="Bind AutoCAD through a known readable DWG when using --dwg-output.")
    parser.add_argument("--page", type=int, default=0, help="Zero-based PDF page index.")
    parser.add_argument("--scale", type=float, default=1.0, help="DXF units per PDF point.")
    parser.add_argument("--bezier-segments", type=int, default=12, help="Line segments per cubic Bezier.")
    parser.add_argument("--no-fills", action="store_true", help="Skip filled black paths such as text outlines.")
    parser.add_argument("--include-white", action="store_true", help="Include white filled paths such as page background.")
    parser.add_argument("--stats", help="Optional JSON stats output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pdf_path = Path(args.pdf).resolve()
    output = Path(args.output).resolve()
    doc = fitz.open(pdf_path)
    if args.page < 0 or args.page >= doc.page_count:
        raise IndexError(f"Page index {args.page} out of range for {doc.page_count} page(s).")
    page = doc[args.page]
    stats = convert_page(page, output, args.scale, max(2, args.bezier_segments), not args.no_fills, args.include_white)
    stats.update(
        {
            "input": str(pdf_path),
            "page": args.page,
            "pdf_page_count": doc.page_count,
            "drawing_count": len(page.get_drawings()),
        }
    )
    if args.dwg_output:
        stats["dwg_output"] = convert_dxf_to_dwg(output, Path(args.dwg_output).resolve(), args.attach_document)
    if args.stats:
        stats_path = Path(args.stats).resolve()
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
