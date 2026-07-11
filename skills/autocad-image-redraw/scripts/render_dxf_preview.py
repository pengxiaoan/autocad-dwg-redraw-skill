#!/usr/bin/env python
"""Audit a DXF and render deterministic fixed-page PNG/PDF previews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, pymupdf, layout

PAGE_MM = {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and render a DXF to a fixed page.")
    parser.add_argument("--dxf", required=True)
    parser.add_argument("--png")
    parser.add_argument("--pdf")
    parser.add_argument("--page", choices=sorted(PAGE_MM), default="A3")
    parser.add_argument("--orientation", choices=["landscape", "portrait"], default="landscape")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--margin-mm", type=float, default=10)
    parser.add_argument("--report")
    args = parser.parse_args()
    if not args.png and not args.pdf:
        parser.error("Provide --png, --pdf, or both.")

    source = Path(args.dxf).expanduser().resolve()
    doc = ezdxf.readfile(source)
    auditor = doc.audit()
    if auditor.has_errors:
        raise SystemExit(f"DXF audit found {len(auditor.errors)} error(s); repair before rendering.")

    width, height = PAGE_MM[args.page]
    if args.orientation == "portrait":
        width, height = min(width, height), max(width, height)
    else:
        width, height = max(width, height), min(width, height)
    page = layout.Page(width, height, layout.Units.mm, margins=layout.Margins.all(args.margin_mm))
    backend = pymupdf.PyMuPdfBackend()
    Frontend(RenderContext(doc), backend).draw_layout(doc.modelspace(), finalize=True)
    pdf_bytes = backend.get_pdf_bytes(page)

    if args.pdf:
        pdf_path = Path(args.pdf).expanduser().resolve()
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf_bytes)
    if args.png:
        png_path = Path(args.png).expanduser().resolve()
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(backend.get_pixmap_bytes(page, fmt="png", dpi=args.dpi, alpha=False))

    counts: dict[str, int] = {}
    layers: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1
        layer_name = entity.dxf.get("layer", "0")
        layers[layer_name] = layers.get(layer_name, 0) + 1
    report = {"tool": "render_dxf_preview/1.0", "status": "pass", "dxf": str(source), "audit_errors": 0, "audit_fixes": len(auditor.fixes), "entity_counts": counts, "layer_counts": layers, "page_mm": [width, height], "dpi": args.dpi}
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
