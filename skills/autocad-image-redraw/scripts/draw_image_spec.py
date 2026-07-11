#!/usr/bin/env python
"""Render an image-derived redraw spec into a DWG through AutoCAD COM."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

pythoncom = None
win32com_client = None

DIMENSION_TYPES = {"linear_dimension", "aligned_dimension", "radial_dimension"}
TEXT_TYPES = {"text", "mtext"}
OMIT_OPTIONS = {"text", "dimensions", "leaders", "table-text", "tables", "borders", "center"}
DEFAULT_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
    r"C:\Windows\Fonts\ARIALUNI.ttf",
]
UNIT_TO_INSUNITS = {"unitless": 0, "in": 1, "ft": 2, "mm": 4, "cm": 5, "m": 6}


def com_retry(action, attempts: int = 30, delay: float = 0.4):
    last_error = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def load_com_modules() -> None:
    global pythoncom, win32com_client
    if pythoncom is not None and win32com_client is not None:
        return
    try:
        import pythoncom as _pythoncom
        import win32com.client as _client
    except ImportError as exc:
        raise SystemExit("pywin32 is required for AutoCAD COM automation. Install with: pip install pywin32") from exc
    try:
        _pythoncom.CoInitialize()
    except Exception:
        pass
    pythoncom = _pythoncom
    win32com_client = _client


def variant_point(coords: list[float] | tuple[float, ...]):
    load_com_modules()
    values = list(coords)
    if len(values) == 2:
        values.append(0.0)
    if len(values) != 3:
        raise ValueError(f"Point must have 2 or 3 values, got {coords!r}")
    return win32com_client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(float(v) for v in values))


def variant_double_array(values: list[float] | tuple[float, ...]):
    load_com_modules()
    return win32com_client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, tuple(float(v) for v in values))


def xy(point: list[float] | tuple[float, ...]) -> tuple[float, float]:
    if len(point) < 2:
        raise ValueError(f"Point must contain x and y, got {point!r}")
    return float(point[0]), float(point[1])


def get_autocad(acad_exe: str | None = None, visible: bool = True, new_instance: bool = False, attach_document: str | None = None):
    load_com_modules()
    acad = None
    if attach_document:
        try:
            attached_doc = win32com_client.GetObject(str(Path(attach_document).resolve()))
            acad = attached_doc.Application
        except Exception:
            acad = None
    if new_instance:
        try:
            acad = win32com_client.DispatchEx("AutoCAD.Application")
        except Exception:
            acad = None
    if acad is None:
        try:
            acad = win32com_client.GetActiveObject("AutoCAD.Application")
        except Exception:
            acad = None
    if acad is None:
        if acad_exe:
            subprocess.Popen([acad_exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + 45
            while time.time() < deadline:
                try:
                    acad = win32com_client.GetActiveObject("AutoCAD.Application")
                    break
                except Exception:
                    time.sleep(1)
        if acad is None:
            acad = win32com_client.Dispatch("AutoCAD.Application")
    try:
        acad.Visible = visible
    except Exception:
        pass
    try:
        acad.WindowState = 3
    except Exception:
        pass
    return acad


def new_document(acad, template: str | None = None):
    if template:
        return com_retry(lambda: acad.Documents.Add(str(Path(template))), attempts=60, delay=0.5)
    return com_retry(lambda: acad.Documents.Add(), attempts=60, delay=0.5)


def load_spec(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict):
        raise ValueError("Spec root must be a JSON object.")
    spec.setdefault("metadata", {})
    spec.setdefault("layers", [])
    spec.setdefault("entities", [])
    if not isinstance(spec["entities"], list):
        raise ValueError("Spec field 'entities' must be a list.")
    return spec


def validate_spec(spec: dict[str, Any]) -> Counter:
    counts = Counter()
    for index, entity in enumerate(spec.get("entities", []), start=1):
        if not isinstance(entity, dict):
            raise ValueError(f"Entity #{index} must be an object.")
        etype = entity.get("type")
        if not etype:
            raise ValueError(f"Entity #{index} is missing 'type'.")
        counts[str(etype)] += 1
        require_fields(index, entity)
    return counts


def resolve_units(spec: dict[str, Any]) -> tuple[str, int]:
    """Resolve declared units without inventing millimeters for unscaled images."""
    metadata = spec.get("metadata", {})
    raw = metadata.get("units", spec.get("units", "unitless"))
    if isinstance(raw, dict):
        raw = raw.get("name", raw.get("unit", "unitless"))
    units = str(raw).strip().lower() or "unitless"
    if units not in UNIT_TO_INSUNITS:
        raise ValueError(f"Unsupported drawing units: {units}. Supported: {', '.join(UNIT_TO_INSUNITS)}")
    return units, UNIT_TO_INSUNITS[units]


def parse_omit_options(args: argparse.Namespace) -> set[str]:
    values: set[str] = set()
    if getattr(args, "geometry_only", False):
        values.update({"text", "dimensions", "leaders", "table-text"})
    raw = getattr(args, "omit", "") or ""
    for value in raw.replace(";", ",").split(","):
        value = value.strip().lower()
        if not value:
            continue
        if value not in OMIT_OPTIONS:
            raise ValueError(f"Unsupported omit option: {value}. Supported: {', '.join(sorted(OMIT_OPTIONS))}")
        values.add(value)
    return values


def should_skip_entity(entity: dict[str, Any], omit: set[str]) -> bool:
    etype = str(entity.get("type", ""))
    layer = str(entity.get("layer", "")).upper()
    if "text" in omit and etype in TEXT_TYPES:
        return True
    if "dimensions" in omit and etype in DIMENSION_TYPES:
        return True
    if "leaders" in omit and etype == "leader":
        return True
    if "tables" in omit and etype == "table":
        return True
    if "borders" in omit and layer == "BORDER":
        return True
    if "center" in omit and (etype == "center_mark" or layer == "CENTER"):
        return True
    return False


def filtered_entities(spec: dict[str, Any], omit: set[str]) -> tuple[list[dict[str, Any]], Counter]:
    kept: list[dict[str, Any]] = []
    skipped = Counter()
    for entity in spec.get("entities", []):
        if should_skip_entity(entity, omit):
            skipped[str(entity.get("type", ""))] += 1
            continue
        prepared = dict(entity)
        if prepared.get("type") == "table" and "table-text" in omit:
            prepared["draw_cell_text"] = False
        kept.append(prepared)
    return kept, skipped


def require_fields(index: int, entity: dict[str, Any]) -> None:
    etype = entity["type"]
    required = {
        "line": ["start", "end"],
        "polyline": ["points"],
        "rectangle": [],
        "circle": ["center", "radius"],
        "arc": ["center", "radius", "start_angle", "end_angle"],
        "text": ["text", "point"],
        "mtext": ["text", "point", "width"],
        "leader": ["points", "text"],
        "linear_dimension": ["p1", "p2", "dimline"],
        "aligned_dimension": ["p1", "p2", "dimline"],
        "radial_dimension": ["center", "chord"],
        "table": ["origin", "col_widths", "row_heights", "cells"],
        "center_mark": ["center"],
    }.get(etype)
    if required is None:
        raise ValueError(f"Entity #{index} has unsupported type: {etype}")
    missing = [field for field in required if field not in entity]
    if missing:
        raise ValueError(f"Entity #{index} ({etype}) is missing fields: {', '.join(missing)}")
    if etype == "rectangle" and not (("p1" in entity and "p2" in entity) or all(k in entity for k in ("x", "y", "width", "height"))):
        raise ValueError("rectangle requires either p1+p2 or x+y+width+height.")


def ensure_layers(doc, spec: dict[str, Any]) -> None:
    defaults = [
        {"name": "OBJECT", "color": 7, "linetype": "Continuous"},
        {"name": "HIDDEN", "color": 8, "linetype": "Hidden"},
        {"name": "CENTER", "color": 4, "linetype": "Center"},
        {"name": "DIM", "color": 7, "linetype": "Continuous"},
        {"name": "TEXT", "color": 7, "linetype": "Continuous"},
        {"name": "TABLE", "color": 7, "linetype": "Continuous"},
        {"name": "CONSTRUCTION", "color": 8, "linetype": "Continuous"},
        {"name": "BORDER", "color": 7, "linetype": "Continuous"},
    ]
    layers = defaults + list(spec.get("layers", []))
    for layer_spec in layers:
        name = str(layer_spec.get("name", "")).strip()
        if not name:
            continue
        try:
            layer = doc.Layers.Item(name)
        except Exception:
            layer = doc.Layers.Add(name)
        if "color" in layer_spec:
            try:
                layer.Color = int(layer_spec["color"])
            except Exception:
                pass
        linetype = layer_spec.get("linetype")
        if linetype:
            try:
                doc.Linetypes.Load(str(linetype), "acad.lin")
            except Exception:
                pass
            try:
                layer.Linetype = str(linetype)
            except Exception:
                pass


def resolve_text_font(requested: str | None = None) -> str | None:
    candidates = []
    if requested:
        candidates.append(requested)
    candidates.extend(DEFAULT_FONT_CANDIDATES)
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def ensure_text_style(doc, style_name: str, font_file: str | None):
    try:
        style = doc.TextStyles.Item(style_name)
    except Exception:
        style = doc.TextStyles.Add(style_name)
    if font_file:
        for attr in ("FontFile", "BigFontFile"):
            try:
                setattr(style, attr, font_file)
            except Exception:
                pass
    try:
        doc.ActiveTextStyle = style
    except Exception:
        pass
    for variable, value in (("TEXTSTYLE", style_name), ("DIMTXSTY", style_name), ("FONTALT", font_file or "")):
        if value:
            try:
                doc.SetVariable(variable, value)
            except Exception:
                pass
    return style


def apply_text_style(obj, entity: dict[str, Any]) -> None:
    style_name = entity.get("text_style") or entity.get("style")
    if not style_name:
        return
    for attr in ("StyleName", "TextStyle", "TextStyleName"):
        try:
            setattr(obj, attr, str(style_name))
            return
        except Exception:
            pass


def apply_props(obj, entity: dict[str, Any]) -> None:
    if "layer" in entity:
        try:
            obj.Layer = str(entity["layer"])
        except Exception:
            pass
    if "color" in entity:
        try:
            obj.Color = int(entity["color"])
        except Exception:
            pass
    if "linetype" in entity:
        try:
            obj.Linetype = str(entity["linetype"])
        except Exception:
            pass


def add_line(space, entity: dict[str, Any]):
    obj = space.AddLine(variant_point(entity["start"]), variant_point(entity["end"]))
    apply_props(obj, entity)
    return [obj]


def add_polyline(space, entity: dict[str, Any]):
    coords: list[float] = []
    points = list(entity["points"])
    if bool(entity.get("closed", False)) and points:
        if xy(points[0]) != xy(points[-1]):
            points.append(points[0])
    for point in points:
        x, y = xy(point)
        coords.extend([x, y])
    obj = space.AddLightWeightPolyline(variant_double_array(coords))
    apply_props(obj, entity)
    return [obj]


def rectangle_points(entity: dict[str, Any]) -> list[list[float]]:
    if "p1" in entity and "p2" in entity:
        x1, y1 = xy(entity["p1"])
        x2, y2 = xy(entity["p2"])
    else:
        x1 = float(entity["x"])
        y1 = float(entity["y"])
        x2 = x1 + float(entity["width"])
        y2 = y1 + float(entity["height"])
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def add_rectangle(space, entity: dict[str, Any]):
    poly = dict(entity)
    poly["type"] = "polyline"
    poly["points"] = rectangle_points(entity)
    poly["closed"] = True
    return add_polyline(space, poly)


def add_circle(space, entity: dict[str, Any]):
    obj = space.AddCircle(variant_point(entity["center"]), float(entity["radius"]))
    apply_props(obj, entity)
    return [obj]


def add_arc(space, entity: dict[str, Any]):
    obj = space.AddArc(
        variant_point(entity["center"]),
        float(entity["radius"]),
        math.radians(float(entity["start_angle"])),
        math.radians(float(entity["end_angle"])),
    )
    apply_props(obj, entity)
    return [obj]


def add_text(space, entity: dict[str, Any]):
    obj = space.AddText(str(entity.get("text", "")), variant_point(entity["point"]), float(entity.get("height", 3.5)))
    if "rotation" in entity:
        obj.Rotation = math.radians(float(entity["rotation"]))
    apply_text_style(obj, entity)
    apply_props(obj, entity)
    return [obj]


def add_mtext(space, entity: dict[str, Any]):
    obj = space.AddMText(variant_point(entity["point"]), float(entity.get("width", 100)), str(entity.get("text", "")))
    if "height" in entity:
        try:
            obj.Height = float(entity["height"])
        except Exception:
            pass
    if "rotation" in entity:
        obj.Rotation = math.radians(float(entity["rotation"]))
    apply_text_style(obj, entity)
    apply_props(obj, entity)
    return [obj]


def add_leader(space, entity: dict[str, Any]):
    made = []
    points = entity["points"]
    for start, end in zip(points, points[1:]):
        line = space.AddLine(variant_point(start), variant_point(end))
        apply_props(line, entity)
        made.append(line)
    if points:
        text_entity = {
            "type": "text",
            "layer": entity.get("text_layer", entity.get("layer", "TEXT")),
            "text": entity.get("text", ""),
            "point": entity.get("text_point", points[-1]),
            "height": entity.get("text_height", entity.get("height", 3.5)),
            "rotation": entity.get("text_rotation", 0),
            "text_style": entity.get("text_style"),
        }
        made.extend(add_text(space, text_entity))
    return made


def add_linear_dimension(space, entity: dict[str, Any]):
    try:
        obj = space.AddDimRotated(
            variant_point(entity["p1"]),
            variant_point(entity["p2"]),
            variant_point(entity["dimline"]),
            math.radians(float(entity.get("angle", 0))),
        )
        if "text" in entity:
            obj.TextOverride = str(entity["text"])
        apply_text_style(obj, entity)
        apply_props(obj, entity)
        return [obj]
    except Exception:
        return add_dimension_fallback(space, entity)


def add_aligned_dimension(space, entity: dict[str, Any]):
    try:
        obj = space.AddDimAligned(variant_point(entity["p1"]), variant_point(entity["p2"]), variant_point(entity["dimline"]))
        if "text" in entity:
            obj.TextOverride = str(entity["text"])
        apply_text_style(obj, entity)
        apply_props(obj, entity)
        return [obj]
    except Exception:
        return add_dimension_fallback(space, entity)


def add_radial_dimension(space, entity: dict[str, Any]):
    try:
        obj = space.AddDimRadial(variant_point(entity["center"]), variant_point(entity["chord"]), float(entity.get("leader", 10)))
        if "text" in entity:
            obj.TextOverride = str(entity["text"])
        apply_text_style(obj, entity)
        apply_props(obj, entity)
        return [obj]
    except Exception:
        center = entity["center"]
        chord = entity["chord"]
        return add_leader(
            space,
            {
                "type": "leader",
                "layer": entity.get("layer", "DIM"),
                "points": [center, chord],
                "text": entity.get("text", ""),
                "text_height": entity.get("text_height", 3.5),
            },
        )


def add_dimension_fallback(space, entity: dict[str, Any]):
    made = []
    line = space.AddLine(variant_point(entity["p1"]), variant_point(entity["p2"]))
    apply_props(line, entity)
    made.append(line)
    label = dict(entity)
    label.update({"type": "text", "point": entity.get("dimline"), "height": entity.get("text_height", 3.5), "text": entity.get("text", "")})
    made.extend(add_text(space, label))
    return made


def add_table(space, entity: dict[str, Any]):
    made = []
    x0, y0 = xy(entity["origin"])
    col_widths = [float(v) for v in entity["col_widths"]]
    row_heights = [float(v) for v in entity["row_heights"]]
    total_w = sum(col_widths)
    total_h = sum(row_heights)
    xs = [x0]
    for width in col_widths:
        xs.append(xs[-1] + width)
    ys = [y0]
    for height in row_heights:
        ys.append(ys[-1] + height)
    for x in xs:
        line = space.AddLine(variant_point([x, y0]), variant_point([x, y0 + total_h]))
        apply_props(line, entity)
        made.append(line)
    for y in ys:
        line = space.AddLine(variant_point([x0, y]), variant_point([x0 + total_w, y]))
        apply_props(line, entity)
        made.append(line)
    if not bool(entity.get("draw_cell_text", True)):
        return made
    cells = entity.get("cells", [])
    text_height = float(entity.get("text_height", 3.0))
    for row_index, row in enumerate(cells):
        if row_index >= len(row_heights):
            break
        y_top = y0 + total_h - sum(row_heights[:row_index])
        y_text = y_top - row_heights[row_index] / 2 - text_height / 2
        for col_index, value in enumerate(row):
            if col_index >= len(col_widths):
                break
            x_text = x0 + sum(col_widths[:col_index]) + float(entity.get("text_padding", 2.0))
            text_entity = {
                "type": "text",
                "layer": entity.get("text_layer", entity.get("layer", "TEXT")),
                "text": str(value),
                "point": [x_text, y_text],
                "height": text_height,
                "text_style": entity.get("text_style"),
            }
            made.extend(add_text(space, text_entity))
    return made


def add_center_mark(space, entity: dict[str, Any]):
    cx, cy = xy(entity["center"])
    size = float(entity.get("size", 10))
    half = size / 2
    made = []
    for start, end in [([cx - half, cy], [cx + half, cy]), ([cx, cy - half], [cx, cy + half])]:
        line = space.AddLine(variant_point(start), variant_point(end))
        apply_props(line, entity)
        made.append(line)
    return made


DRAWERS = {
    "line": add_line,
    "polyline": add_polyline,
    "rectangle": add_rectangle,
    "circle": add_circle,
    "arc": add_arc,
    "text": add_text,
    "mtext": add_mtext,
    "leader": add_leader,
    "linear_dimension": add_linear_dimension,
    "aligned_dimension": add_aligned_dimension,
    "radial_dimension": add_radial_dimension,
    "table": add_table,
    "center_mark": add_center_mark,
}


def render_spec(spec: dict[str, Any], output: Path, args: argparse.Namespace) -> Counter:
    acad = get_autocad(args.acad_exe, visible=not args.hidden, new_instance=args.new_instance, attach_document=args.attach_document)
    doc = new_document(acad, args.template)
    try:
        _units, insunits = resolve_units(spec)
        doc.SetVariable("INSUNITS", insunits)
        doc.SetVariable("LUNITS", 2)
    except Exception:
        pass
    ensure_layers(doc, spec)
    font_file = resolve_text_font(args.text_font)
    ensure_text_style(doc, args.text_style, font_file)
    space = doc.PaperSpace if args.space == "paper" else doc.ModelSpace
    drawn = Counter()
    omit = parse_omit_options(args)
    entities, _skipped = filtered_entities(spec, omit)
    for index, entity in enumerate(entities, start=1):
        etype = entity["type"]
        if etype in TEXT_TYPES or etype in DIMENSION_TYPES or etype in {"leader", "table"}:
            entity.setdefault("text_style", args.text_style)
        drawer = DRAWERS[etype]
        try:
            made = drawer(space, entity)
        except Exception as exc:
            raise RuntimeError(f"Failed drawing entity #{index} ({etype}): {exc}") from exc
        drawn[etype] += len(made)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"Output exists; pass --overwrite to replace it: {output}")
    if output.exists() and args.overwrite:
        output.unlink()
    doc.SaveAs(str(output))
    try:
        acad.ZoomExtents()
    except Exception:
        pass
    return drawn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an image-derived AutoCAD redraw spec to DWG.")
    parser.add_argument("--spec", required=True, help="Path to the JSON redraw spec.")
    parser.add_argument("--output", help="Output DWG path. Required unless --dry-run is used.")
    parser.add_argument("--acad-exe", help="Optional acad.exe path to start AutoCAD if no running instance is available.")
    parser.add_argument("--template", help="Optional AutoCAD template path for Documents.Add().")
    parser.add_argument("--space", choices=["model", "paper"], default="model", help="Target AutoCAD space. Default: model.")
    parser.add_argument("--hidden", action="store_true", help="Keep AutoCAD hidden while drawing.")
    parser.add_argument("--new-instance", action="store_true", help="Start a new AutoCAD COM instance instead of reusing the active one.")
    parser.add_argument("--attach-document", help="Bind through a specific DWG document to avoid AutoCAD Start-page or multi-instance COM confusion.")
    parser.add_argument("--text-style", default="CN_TEXT", help="AutoCAD text style name for Chinese-safe text. Default: CN_TEXT.")
    parser.add_argument("--text-font", help="Chinese-capable font file path. Defaults to common Windows Chinese fonts.")
    parser.add_argument("--geometry-only", action="store_true", help="Draw only visible geometry. Omit text, dimensions, leaders, and table cell text.")
    parser.add_argument(
        "--omit",
        default="",
        help="Comma-separated optional omissions: text, dimensions, leaders, table-text, tables, borders, center.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace output DWG if it already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize the spec without connecting to AutoCAD.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    spec_path = Path(args.spec).expanduser().resolve()
    spec = load_spec(spec_path)
    counts = validate_spec(spec)
    units, insunits = resolve_units(spec)
    omit = parse_omit_options(args)
    entities, skipped = filtered_entities(spec, omit)
    effective_counts = Counter(str(entity.get("type", "")) for entity in entities)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "spec": str(spec_path),
                    "source_entity_counts": counts,
                    "source_entity_total": sum(counts.values()),
                    "units": units,
                    "insunits": insunits,
                    "omit": sorted(omit),
                    "effective_entity_counts": effective_counts,
                    "effective_entity_total": sum(effective_counts.values()),
                    "skipped_entity_counts": skipped,
                    "skipped_entity_total": sum(skipped.values()),
                },
                indent=2,
            )
        )
        return 0
    if not args.output:
        parser.error("--output is required unless --dry-run is used.")
    output = Path(args.output).expanduser().resolve()
    drawn = render_spec(spec, output, args)
    print(
        json.dumps(
            {
                "output": str(output),
                "units": units,
                "insunits": insunits,
                "omit": sorted(omit),
                "effective_entity_counts": effective_counts,
                "skipped_entity_counts": skipped,
                "drawn_counts": drawn,
                "drawn_total": sum(drawn.values()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
