---
name: autocad-dwg-redraw
description: Rebuild and validate AutoCAD drawings from a source DWG, a PDF-derived intermediate DWG, or a raster reference image paired with authoritative dimensions and drawing requirements. Use when Codex must profile and exactly reproduce a .dwg, convert a PDF into a validated intermediate DWG before exact redraw, or convert an image plus metrics into parameter-driven AutoLISP/AutoCAD geometry and optional 3D solids.
---

# AutoCAD DWG Redraw

Use one of three input modes, then validate the resulting DWG:

1. **Source DWG mode:** profile a DWG, generate a standardized drawing-specific prompt, and reproduce it exactly.
2. **PDF-derived DWG mode:** convert a PDF into an auditable intermediate DWG, then use the Source DWG flow to rebuild and validate that intermediate drawing.
3. **Image + metrics mode:** normalize the reference image and authoritative dimensions into a parameter specification, generate AutoLISP or COM geometry, and validate the result against both the metrics and visible layout.

## Core Rule

Do not infer a complex DWG from screenshots or visual style alone when the source DWG is available. First extract or copy actual source entities, then validate against the original.

For final delivery, prefer exact DWG entity copy through AutoCAD COM. Generated AutoLISP/Python reconstruction should only be used when the user specifically needs auditable source code and exact extracted entity data is available.

For image + metrics input, treat supplied dimensions, units, counts, and layout constraints as authoritative. Use image pixels only to identify topology, ordering, visual relationships, and unspecified details. When the image conflicts with a supplied metric, follow the metric and report the discrepancy.

For PDF input, do not claim exact source-DWG fidelity unless an original DWG is available. First identify what the PDF contains: extractable vector paths, embedded raster images, extractable text, or a mix of these. Convert that evidence into an intermediate DWG, document the conversion limits, and then validate the intermediate DWG with the normal DWG redraw workflow.

## Source DWG Flow

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

## PDF-Derived DWG Flow

Use this mode when the user provides a PDF and no source DWG is available. The goal is a reproducible CAD redraw from PDF evidence, followed by normal DWG validation against the generated intermediate DWG.

1. **Inspect the PDF content**
   - Record page count, page size, units if known, creation/producer metadata, extractable text count, embedded image count, and whether vector drawing paths are available.
   - Prefer vector PDF paths over raster tracing when available.
   - If the PDF is mostly raster, render the page at high DPI and treat the result as visual evidence rather than exact CAD source data.
2. **Create an intermediate CAD file**
   - For vector PDFs, convert paths to DXF/DWG with units calibrated from the PDF page size or explicit sheet dimensions.
   - For raster or mixed PDFs, use high-DPI rasterization, linework/vectorization, and text extraction where available. Write text as real `TEXT`/`MTEXT` only when it is extractable or OCR-confirmed; otherwise preserve it as traced geometry or mark it as uncertain.
   - Use generic layers such as `LINEWORK`, `TEXT`, `BORDER`, `DIM`, `CENTER`, and `CONSTRUCTION`, unless the PDF or user supplies a layer convention.
   - Save the intermediate DWG without overwriting the PDF or any original DWG.
3. **Profile the intermediate DWG**
   ```powershell
   python path\to\scripts\dwg_prompt_builder.py --source intermediate.dwg --output intermediate-redraw-prompt.md
   ```
4. **Rebuild and validate with the Source DWG flow**
   ```powershell
   python path\to\scripts\dwg_redraw.py --source intermediate.dwg --output outputs\redraw_from_pdf.dwg
   ```
   Validation is expected to match the intermediate DWG's entity counts and object distribution. Also visually compare the intermediate and final DWG against the original PDF.
5. **Report conversion limits**
   State whether geometry came from vector PDF paths, raster tracing, OCR/text extraction, or inference. Call out unreadable text, non-editable traced text, approximate curves, missing dimensions, and any scale assumptions.

## Image + Metrics Flow

Use this mode when the user supplies one or more PNG/JPG/JPEG references plus written dimensions or a parameter table.

1. **Normalize the input specification**
   Record image paths, units, overall dimensions, repeated module dimensions, thicknesses, offsets, feature counts, internal layouts, required views, layers, annotations, 3D requirements, output paths, and tolerances. Mark every missing value as an explicit unknown instead of guessing silently.
2. **Resolve geometry authority**
   Apply written metrics first, derived arithmetic second, and image proportions third. Confirm calculated clearances and repeated-module totals before drawing.
3. **Plan the AutoCAD build**
   Prefer AutoLISP for auditable parameter-driven construction. Use Python only for parameter-file generation or AutoCAD COM orchestration. Create all requested layers, text/dimension styles, groups, views, and save targets deterministically.
4. **Draw deterministically**
   Build setup, primary outlines, internal geometry, annotation, and 3D solids in auditable stages. Keep the construction repeatable so the same parameters produce the same DWG.
5. **Validate and deliver**
   Check positive dimensions, arithmetic totals, object bounds, unintended overlaps, required layers, entity/solid counts, named groups, requested views, and final DWG save status. Compare the finished drawing visually with the reference image without overriding authoritative metrics.

When `autocad-image-redraw` is installed, use its visual-analysis conventions for image topology and visible annotations while retaining this skill's parameter authority, AutoLISP/COM build, and DWG validation contract.

### Minimum Parameter Specification

- Reference image path or paths.
- Unit system and overall width, height, and depth where applicable.
- Component dimensions, thicknesses, offsets, counts, and repeated spacing rules.
- Required 2D views, 3D solids, layers, dimensions, text, blocks, and named groups.
- Output DWG path.
- Explicit assumptions and tolerances for details not specified by metrics.

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
- In PDF-derived DWG mode, clearly distinguish exact vector conversion, raster/vector tracing, text extraction/OCR, and inferred geometry.
- Do not present a PDF-derived intermediate DWG as an exact original CAD source.
- In image + metrics mode, reject negative or zero construction dimensions, out-of-bound components, unexplained overlaps, and arithmetic totals that do not match the supplied overall size.
- Never use image proportions to replace a supplied numerical dimension.
- Preserve a parameter block or parameter file so the drawing can be regenerated with changed dimensions.

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
