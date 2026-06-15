# DWG Redraw Prompt Template

Use this template when the user wants generated AutoLISP or Python code rather than direct entity copying.

## Required Source Data

Ask the user to extract these from AutoCAD before generating code:

- Drawing units and precision.
- Drawing extents or sheet size.
- Layer table: name, color, linetype, lineweight, purpose.
- Text styles: font, big font, height, width factor, oblique angle.
- Dimension styles: arrow size, text height, precision, scale.
- Block definitions and insertions: name, base point, attributes, insertion point, scale, rotation.
- Entities grouped by layer:
  - `LINE`: start and end points.
  - `LWPOLYLINE`: vertices, closure, widths, bulges.
  - `CIRCLE`: center and radius.
  - `ARC`: center, radius, start angle, end angle.
  - `TEXT/MTEXT`: insertion point, content, height, rotation, style.
  - `HATCH`: boundary, pattern, scale, angle.
  - Dimensions: type, definition points, text location.

## Prompt Skeleton

```text
You are a senior AutoCAD automation engineer.

Task:
Create a complete redraw program for [DRAWING_NAME]. The output must match the source DWG in geometry, layers, dimensions, text, blocks, title block, and visible layout.

Environment:
- AutoCAD 2018 or newer on Windows
- Units: [mm/inch]
- Coordinate system: WCS
- Drawing limits/extents: [minX,minY] to [maxX,maxY]

Layers:
[paste layer table]

Text styles:
[paste style table]

Dimension styles:
[paste dimension style table]

Blocks:
[paste block definitions and attributes]

Entities:
[paste entity list grouped by layer]

Requirements:
1. Do not omit entities.
2. Use exact coordinates from the extracted data.
3. Use existing layers/styles/blocks before drawing.
4. Restore AutoCAD system variables after running.
5. Print entity counts at the end.
6. Add TODO comments only where the extracted source data is insufficient.
```

## Practical Guidance

- Prefer direct DWG entity copying for final fidelity when AutoCAD is available.
- Use generated AutoLISP/Python only when the user needs auditable source code or parametric reconstruction.
- If only screenshots are available, label the result as an approximation, not an exact redraw.
