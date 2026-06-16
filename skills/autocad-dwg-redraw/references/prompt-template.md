# DWG Redraw Prompt Template

Use this template to generate a drawing-specific custom redraw prompt from any source DWG.

The goal is to produce a reusable `DRAWING_NAME-redraw-prompt.md` file that can drive either:

- exact DWG-to-DWG redraw through AutoCAD COM, or
- generated AutoLISP/Python redraw code when full extracted entity data is available.

## Standard Custom Prompt Structure

Every custom prompt must use this structure:

1. **Drawing fingerprint**
   - Source file name
   - DWG version if known
   - File size
   - ModelSpace entity count
   - PaperSpace entity count
   - Object type distribution
   - Dimension/leader count
   - Annotation count
2. **Drawing classification**
   - Part drawing / assembly drawing / layout sheet / manufacturing drawing / unknown
   - Reasoning based on blocks, BOM names, title blocks, dimensions, leaders, and symbols
3. **Global redraw policy**
   - Use exact AutoCAD COM copy for final delivery
   - Never overwrite the source DWG
   - Preserve dimensions, leaders, annotations, blocks, layers, and layouts
4. **Environment**
   - Windows + AutoCAD
   - Python 3.10+
   - pywin32
5. **Layer inventory**
   - name, color, linetype, lineweight
6. **Style inventory**
   - text styles
   - dimension styles
7. **Annotation inventory**
   - dimensions
   - leaders
   - text / MTEXT
   - datum, tolerance, and surface finish symbols
8. **Block inventory**
   - title blocks
   - BOM/detail table blocks
   - surface finish symbols
   - datum/tolerance symbols
   - custom annotation blocks
9. **Entity extraction plan**
   - DXFOUT
   - DATAEXTRACTION
   - LIST
   - LAYER/STYLE/DIMSTYLE listing
10. **Execution commands**
   - prompt generation command
   - validated redraw command
11. **Validation**
   - ModelSpace entity equality
   - PaperSpace entity equality
   - dimension/leader equality
   - annotation equality
   - visual `ZOOM EXTENTS` check
   - title block/BOM/block/text/dimension check

## Required Source Data For Code-Level Redraw

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
  - Dimensions: type, definition points, text location, style, scale, precision, overrides.
  - Leaders: vertices, arrowheads, attached annotation, style.

## Prompt Skeleton

```text
# Role
You are a senior AutoCAD automation engineer and mechanical drafting specialist.

# Task
Create a custom redraw workflow for [DRAWING_NAME]. The output must match the source DWG in geometry, layers, dimensions, leaders, text, blocks, title block, and visible layout.

# Drawing Fingerprint
- Source DWG: [FILE_NAME]
- File size: [SIZE]
- ModelSpace entity count: [COUNT]
- PaperSpace entity count: [COUNT]
- Dimension/leader count: [COUNT]
- Annotation count: [COUNT]
- Object type distribution:
[OBJECT_TYPE_COUNTS]

# Drawing Classification
[PART / ASSEMBLY / LAYOUT / MANUFACTURING / UNKNOWN]
[brief reason]

# Global Redraw Policy
- Use exact DWG entity copy for final delivery when AutoCAD is available.
- Do not overwrite the source DWG.
- Preserve dimensions, leaders, annotations, layers, blocks, and layouts.
- Validate source and target entity counts.

# Environment
- AutoCAD 2018 or newer on Windows
- Units: [mm/inch]
- Coordinate system: WCS
- Drawing limits/extents: [minX,minY] to [maxX,maxY]

# Layers
[paste layer table]

# Text Styles
[paste style table]

# Dimension Styles
[paste dimension style table]

# Blocks
[paste block definitions and attributes]

# Entity Extraction Plan
- Use DXFOUT for text DXF when generated code is required.
- Use DATAEXTRACTION for exact coordinate tables.
- Use LIST for selected complex objects.
- Use -LAYER, -STYLE, and -DIMSTYLE listings for standards.

# Entities
[paste entity list grouped by layer]

# Execution Commands
Generate prompt:
python scripts\dwg_prompt_builder.py --source "[FILE_NAME]" --output "outputs\[BASENAME]-redraw-prompt.md"

Validated redraw:
python scripts\dwg_redraw.py --source "[FILE_NAME]" --output "outputs\[BASENAME]_redraw_exact.dwg"

# Requirements
1. Do not omit entities.
2. Do not omit dimensions, leaders, text, MTEXT, title blocks, or BOM/detail tables.
3. Use exact coordinates from the extracted data when generating code.
4. Use existing layers/styles/blocks before drawing when generating code.
5. Restore AutoCAD system variables after running generated code.
6. Print entity, dimension, leader, and annotation counts at the end.
7. Add TODO comments only where extracted source data is insufficient.

# Validation
- Source ModelSpace entity count must equal final target ModelSpace entity count.
- Source PaperSpace entity count must equal final target PaperSpace entity count.
- Source dimension/leader count must equal final target dimension/leader count.
- Source annotation count must equal final target annotation count.
- ZOOM EXTENTS must show the complete drawing.
- Title block, BOM, dimensions, leaders, text, and custom blocks must visually match.
```

## Practical Guidance

- Prefer direct DWG entity copying for final fidelity when AutoCAD is available.
- Use generated AutoLISP/Python only when the user needs auditable source code or parametric reconstruction.
- If only screenshots are available, label the result as an approximation, not an exact redraw.
