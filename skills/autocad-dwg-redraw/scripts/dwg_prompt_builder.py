"""Generate a standardized custom redraw prompt for a source AutoCAD DWG."""

from __future__ import annotations

import argparse
import collections
import subprocess
import sys
import time
from pathlib import Path

import win32com.client


ANNOTATION_TYPES = ("Dimension", "Leader", "Text", "MText", "Tolerance")


def com_retry(action, attempts: int = 30, delay: float = 0.4):
    last_error = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def connect_autocad():
    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        print("Connected to running AutoCAD.")
    except Exception:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        print("Started AutoCAD.")
    try:
        acad.Visible = True
    except Exception as exc:
        print(f"Warning: could not set AutoCAD visible: {exc}")
    return acad


def restart_autocad(acad_exe: str | None = None, wait: float = 15.0):
    subprocess.run(["taskkill", "/IM", "acad.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    if acad_exe:
        subprocess.Popen([acad_exe])
        time.sleep(wait)
    return connect_autocad()


def connect_or_restart_autocad(restart: bool = False, acad_exe: str | None = None):
    return restart_autocad(acad_exe=acad_exe) if restart else connect_autocad()


def find_or_open_document(acad, source_path: Path):
    source_path = source_path.resolve()
    try:
        count = com_retry(lambda: acad.Documents.Count)
        for index in range(count):
            doc = com_retry(lambda idx=index: acad.Documents.Item(idx))
            full_name = str(getattr(doc, "FullName", "") or "")
            if full_name.lower() == str(source_path).lower():
                com_retry(lambda: doc.ModelSpace.Count, attempts=40, delay=0.5)
                return doc
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        com_retry(lambda: active.ModelSpace.Count, attempts=40, delay=0.5)
        return active

    com_retry(lambda: acad.Documents.Open(str(source_path)), attempts=5, delay=2.0)
    opened = com_retry(lambda: acad.ActiveDocument)
    com_retry(lambda: opened.ModelSpace.Count, attempts=60, delay=0.5)
    return opened


def safe_get(obj, attr: str, default=""):
    try:
        value = getattr(obj, attr)
        return value if value is not None else default
    except Exception:
        return default


def collect_layers(doc):
    rows = []
    try:
        count = doc.Layers.Count
        for index in range(count):
            layer = doc.Layers.Item(index)
            rows.append(
                {
                    "name": safe_get(layer, "Name"),
                    "color": safe_get(layer, "Color"),
                    "linetype": safe_get(layer, "Linetype"),
                    "lineweight": safe_get(layer, "Lineweight"),
                }
            )
    except Exception as exc:
        rows.append({"name": f"ERROR: {exc}", "color": "", "linetype": "", "lineweight": ""})
    return rows


def collect_named_collection(collection, name_attr="Name"):
    names = []
    try:
        count = collection.Count
        for index in range(count):
            item = collection.Item(index)
            names.append(str(safe_get(item, name_attr)))
    except Exception as exc:
        names.append(f"ERROR: {exc}")
    return names


def collect_entity_counts(space):
    counts = collections.Counter()
    layers = collections.Counter()
    total = com_retry(lambda: space.Count)
    for index in range(total):
        entity = com_retry(lambda idx=index: space.Item(idx))
        counts[str(safe_get(entity, "ObjectName", "UNKNOWN"))] += 1
        layers[str(safe_get(entity, "Layer", "UNKNOWN"))] += 1
    return total, counts, layers


def annotation_total(counts: collections.Counter) -> int:
    return sum(count for name, count in counts.items() if any(token in name for token in ANNOTATION_TYPES))


def dimension_total(counts: collections.Counter) -> int:
    return sum(count for name, count in counts.items() if "Dimension" in name or "Leader" in name)


def classify_drawing(block_names, entity_counts):
    upper_blocks = [name.upper() for name in block_names]
    has_bom = any("BOM" in name or "BILL" in name for name in upper_blocks)
    has_title = any("A0" in name or "A1" in name or "A2" in name or "A3" in name or "TITLE" in name for name in upper_blocks)
    has_dimensions = dimension_total(entity_counts) > 0
    if has_bom:
        return "assembly or layout drawing", "BOM-related block names were detected."
    if has_title:
        return "layout sheet or manufacturing drawing", "Title-block-like block names were detected."
    if has_dimensions:
        return "manufacturing/detail drawing", "Dimension or leader entities were detected."
    return "unknown or geometry-only drawing", "No clear BOM, title block, or dimension signal was detected."


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def render_prompt(source_path, doc, layers, text_styles, dim_styles, blocks, model_total, paper_total, entity_counts, layer_counts):
    classification, reason = classify_drawing(blocks, entity_counts)
    basename = source_path.stem
    file_size = source_path.stat().st_size

    entity_rows = [{"ObjectName": name, "Count": count} for name, count in entity_counts.most_common()]
    layer_count_rows = [{"Layer": name, "EntityCount": count} for name, count in layer_counts.most_common()]
    block_rows = [{"BlockName": name} for name in blocks]
    style_rows = [{"TextStyle": name} for name in text_styles]
    dim_rows = [{"DimStyle": name} for name in dim_styles]

    return f"""# {basename} Custom DWG Redraw Prompt

## 1. Drawing Fingerprint

- Source DWG: `{source_path.name}`
- File size: {file_size} bytes
- AutoCAD document name: `{safe_get(doc, "Name")}`
- ModelSpace entity count: {model_total}
- PaperSpace entity count: {paper_total}
- Initial classification: {classification}
- Classification reason: {reason}
- Dimension/leader count: {dimension_total(entity_counts)}
- Annotation count: {annotation_total(entity_counts)}

## 2. Required Redraw Strategy

- Use exact AutoCAD COM entity copy for the final deliverable.
- Copy ModelSpace and PaperSpace unless the user explicitly requests ModelSpace only.
- Do not omit dimensions, leaders, text, MTEXT, hatches, block references, title blocks, or BOM/detail tables.
- Do not overwrite the source DWG; write all outputs to `outputs/` or another user-specified directory.
- If generated AutoLISP/Python source code is required, first extract exact entity data with DXFOUT or DATAEXTRACTION.

## 3. Recommended Commands

Generate this custom prompt:

```powershell
python scripts\\dwg_prompt_builder.py --source "{source_path.name}" --output "outputs\\{basename}-redraw-prompt.md"
```

Create the validated redraw:

```powershell
python scripts\\dwg_redraw.py --source "{source_path.name}" --output "outputs\\{basename}_redraw_exact.dwg" --restart-autocad --acad-exe "C:\\Path\\To\\acad.exe"
```

## 4. Layers

{markdown_table(["name", "color", "linetype", "lineweight"], layers)}

## 5. Entity Type Distribution

{markdown_table(["ObjectName", "Count"], entity_rows)}

## 6. Entity Layer Distribution

{markdown_table(["Layer", "EntityCount"], layer_count_rows)}

## 7. Blocks

{markdown_table(["BlockName"], block_rows)}

## 8. Text Styles

{markdown_table(["TextStyle"], style_rows)}

## 9. Dimension Styles

{markdown_table(["DimStyle"], dim_rows)}

## 10. Data Required For Code-Level Redraw

Run these AutoCAD commands when exact generated code is required:

```text
DXFOUT
DATAEXTRACTION
-LAYER ? *
-STYLE ? *
-DIMSTYLE ? *
LIST
```

Extract:

- Exact coordinates for LINE/LWPOLYLINE/CIRCLE/ARC/TEXT/MTEXT/HATCH/DIMENSION entities.
- Dimension type, definition points, text location, style, scale, precision, and overrides.
- Leader vertices, arrowheads, annotation text, and attached blocks.
- Block definitions, insertion points, scale, rotation, and attributes.
- Title block, BOM/detail table, tolerance, datum, and surface finish symbols.
- Legacy SHX font and big-font settings.

## 11. Validation Criteria

- Source ModelSpace entity count equals target ModelSpace entity count: {model_total}
- Source PaperSpace entity count equals target PaperSpace entity count: {paper_total}
- Source dimension/leader count equals target dimension/leader count: {dimension_total(entity_counts)}
- Source annotation count equals target annotation count: {annotation_total(entity_counts)}
- Object type distribution matches source.
- `ZOOM EXTENTS` shows the complete drawing.
- Title block, BOM/detail tables, dimensions, leaders, text, MTEXT, centerlines, hidden lines, and section lines visually match.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a standardized DWG redraw custom prompt.")
    parser.add_argument("--source", required=True, help="Source DWG file.")
    parser.add_argument("--output", help="Output Markdown prompt path.")
    parser.add_argument("--restart-autocad", action="store_true", help="Restart AutoCAD before opening the source DWG.")
    parser.add_argument("--acad-exe", help="Optional acad.exe path used with --restart-autocad.")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source DWG not found: {source_path}")

    output_path = Path(args.output).resolve() if args.output else source_path.with_name(f"{source_path.stem}-redraw-prompt.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    acad = connect_or_restart_autocad(restart=args.restart_autocad, acad_exe=args.acad_exe)
    doc = find_or_open_document(acad, source_path)
    model_total, entity_counts, layer_counts = collect_entity_counts(doc.ModelSpace)
    paper_total = com_retry(lambda: doc.PaperSpace.Count)
    layers = collect_layers(doc)
    text_styles = collect_named_collection(doc.TextStyles)
    dim_styles = collect_named_collection(doc.DimStyles)
    blocks = collect_named_collection(doc.Blocks)

    prompt = render_prompt(
        source_path,
        doc,
        layers,
        text_styles,
        dim_styles,
        blocks,
        model_total,
        paper_total,
        entity_counts,
        layer_counts,
    )
    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote custom redraw prompt: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Prompt generation failed: {exc}", file=sys.stderr)
        raise
