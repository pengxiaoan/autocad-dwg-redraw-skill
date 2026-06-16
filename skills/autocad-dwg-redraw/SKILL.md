---
name: autocad-dwg-redraw
description: Create standardized custom redraw prompts for AutoCAD DWG files, then rebuild and validate DWGs using AutoCAD COM automation. Use when Codex is given a source .dwg and must profile it, generate a drawing-specific redraw prompt, reproduce it as a new DWG, and compare geometry, annotation, layer, block, and entity counts.
---

# AutoCAD DWG Redraw

Use this skill in two stages:

1. Generate a standardized drawing-specific redraw prompt from a source DWG.
2. Use that prompt and the bundled redraw script to rebuild and validate the DWG.

## Core Rule

Do not infer a complex DWG from screenshots or visual style alone when the source DWG is available. First extract or copy actual source entities, then validate against the original.

For final delivery, prefer exact DWG entity copy through AutoCAD COM. Generated AutoLISP/Python reconstruction should only be used when the user specifically needs auditable source code and exact extracted entity data is available.

## Standard User Flow

When the user provides a DWG, follow this repeatable flow:

1. **Profile the source DWG**
   ```powershell
   python path\to\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md --restart-autocad --acad-exe "C:\Path\To\acad.exe"
   ```
2. **Review the generated custom prompt**
   Confirm drawing name, entity counts, layer table, block inventory, text styles, dimension styles, annotation counts, and risk notes.
3. **Create the accurate redraw**
   ```powershell
   python path\to\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --restart-autocad --acad-exe "C:\Path\To\acad.exe"
   ```
4. **Validate**
   Compare source and target ModelSpace/PaperSpace entity counts, object-type distribution, dimension/leader counts, text/MTEXT counts, block references, layers, and visual layout.

## Redraw Prompt Standard

Every generated custom prompt must include:

- File identity: source file name, DWG version if known, entity counts, and ModelSpace/PaperSpace counts.
- Drawing classification: part drawing, assembly drawing, layout/title-block drawing, or unknown.
- Required workflow: exact AutoCAD COM copy for final delivery; generated code only when exact extracted entity data is provided.
- Environment assumptions: Windows, AutoCAD, Python, COM, and `pywin32`.
- Layer table: layer names, colors, linetypes, and lineweights when available.
- Style table: text styles and dimension styles when available.
- Annotation inventory: dimension entities, leaders, text, MTEXT, tolerances, datum/surface-finish symbols, and any annotation blocks.
- Block inventory: block names, especially title blocks, BOM tables, datum symbols, surface finish symbols, and custom annotation blocks.
- Entity distribution: counts by AutoCAD object type and by space.
- Extraction requirements: DXFOUT/DATAEXTRACTION/LIST instructions when generated source code is requested.
- Validation criteria: source-target entity count comparison, dimension/leader comparison, visual check with ZOOM EXTENTS, and title block/BOM/block verification.
- Known risks: legacy encodings, SHX fonts, associative annotations, annotative dimensions, nested blocks, xrefs, proxy objects, and layout-specific objects.

Use `references/prompt-template.md` as the template when composing the custom prompt manually. Prefer `scripts/dwg_prompt_builder.py` when AutoCAD COM is available.

## Accuracy Requirements

- Copy ModelSpace entities and PaperSpace entities unless the user explicitly requests ModelSpace only.
- Preserve dimensions, leaders, text, MTEXT, hatches, blocks, layers, linetypes, colors, lineweights, text styles, and dimension styles.
- Treat missing dimensions or leaders as a validation failure when the source contains them.
- Do not overwrite the source DWG. Always write to a new output path.
- If a drawing uses xrefs, proxy objects, custom objects, or annotative dimensions, report the risk and validate visually in AutoCAD.

## AutoCAD Stability Notes

- If AutoCAD COM returns "call was rejected by callee" or document collections become unreadable, wait briefly and retry. If it persists, close extra AutoCAD windows and restart AutoCAD.
- If AutoCAD opens only the Start page or `Documents.Count`, `ActiveDocument.Name`, `Documents.Open`, or `ModelSpace` fails with `<unknown>`, use `--restart-autocad --acad-exe "path\to\acad.exe"` so the script starts from a clean AutoCAD process.
- Some AutoCAD versions return a method proxy such as `<COMObject Open>` from `Documents.Open()` instead of a document object. After opening, use `ActiveDocument` and verify `ActiveDocument.ModelSpace.Count`.
- For legacy DWGs, let AutoCAD finish loading before reading COM collections. If the window title changes but COM is not ready, wait and retry or restart.
- Old DWGs may use legacy encodings and custom SHX fonts. Preserve source entities rather than recreating text by guessing.

## Source Data Extraction

When exact entity copy is not acceptable and the user truly needs generated source code, extract structured data first:

- `DXFOUT`: export text DXF and inspect `TABLES`, `BLOCKS`, and `ENTITIES`.
- `DATAEXTRACTION`: export entity coordinates, radii, lengths, layers, and block attributes.
- `-LAYER ? *`: list layers, colors, linetypes, and lineweights.
- `-STYLE ? *`: list text styles and fonts.
- `-DIMSTYLE ? *`: list dimension style settings.
- `LIST`: inspect selected entity geometry.

Use `references/prompt-template.md` for a compact prompt template when generating AutoLISP or Python redraw code from extracted data.

## Bundled Scripts

Use `scripts/dwg_prompt_builder.py` to generate a drawing-specific prompt:

```powershell
python scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
python scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md --restart-autocad --acad-exe "C:\Path\To\acad.exe"
```

Use `scripts/dwg_redraw.py` for deterministic AutoCAD COM redraw and validation:

```powershell
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --restart-autocad --acad-exe "C:\Path\To\acad.exe"
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_modelspace_only.dwg --modelspace-only
```

The scripts require Windows, AutoCAD, Python 3.10+, and `pywin32`.
