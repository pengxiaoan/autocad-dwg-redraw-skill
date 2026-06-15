---
name: autocad-dwg-redraw
description: Create standardized custom redraw prompts for AutoCAD DWG files, then rebuild, validate, and screen-record DWG redraws using AutoCAD COM automation. Use when Codex is given any source .dwg and must profile it, generate a drawing-specific redraw prompt, reproduce it as a new DWG, compare entity counts, or create a video-friendly redraw demo.
---

# AutoCAD DWG Redraw

Use this skill in two stages:

1. Generate a standardized drawing-specific redraw prompt from a source DWG.
2. Use that prompt and the bundled redraw script to rebuild, validate, and optionally record the DWG.

## Core Rule

Do not infer a complex DWG from screenshots or visual style alone when the source DWG is available. First extract or copy actual source entities, then validate against the original.

For final delivery, prefer exact entity copy. For videos, use batch redraw with delays, then clearly label it as a demonstration copy.

## Standard User Flow

When the user provides only a DWG, follow this repeatable flow:

1. **Profile the source DWG**
   ```powershell
   python path\to\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
   ```
2. **Review the generated custom prompt**
   Confirm drawing name, entity counts, layers, blocks, text styles, dimension styles, and risk notes.
3. **Create the final accurate redraw**
   ```powershell
   python path\to\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
   ```
4. **Create a video-friendly redraw when needed**
   ```powershell
   python path\to\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_recorded.dwg --batch-size 22 --step-delay 0.45 --record
   ```
5. **Validate**
   Compare source and target entity counts. Use the exact redraw as the deliverable. Use the recorded redraw as video material.

## Redraw Prompt Standard

Every generated custom prompt must include:

- File identity: source file name, DWG version if known, entity counts, and ModelSpace/PaperSpace counts.
- Drawing classification: part drawing, assembly drawing, layout/title-block drawing, or unknown.
- Required workflow: exact mode for final delivery; batch mode only for visible redraw videos.
- Environment assumptions: Windows, AutoCAD, Python, COM, and required Python packages.
- Layer table: layer names, colors, linetypes, and lineweights when available.
- Style table: text styles and dimension styles when available.
- Block inventory: block names, especially title blocks, BOM tables, datum symbols, surface finish symbols, and custom annotation blocks.
- Entity distribution: counts by AutoCAD object type and by space.
- Extraction requirements: DXFOUT/DATAEXTRACTION/LIST instructions when generated source code is requested.
- Validation criteria: source-target entity count comparison, visual check with ZOOM EXTENTS, and title block/BOM/block verification.
- Known risks: legacy encodings, SHX fonts, associative annotations, nested blocks, xrefs, proxy objects, and batch-copy duplicate dependencies.

Use `references/prompt-template.md` as the template when composing the custom prompt manually. Prefer `scripts/dwg_prompt_builder.py` when AutoCAD COM is available.

## Choosing A Mode

- **Exact mode (`--exact`)**: One copy operation for all ModelSpace entities. Use for final comparison and delivery. This avoids duplicate dependent blocks that can appear when associative leaders, dimensions, or custom blocks are copied in batches.
- **Batch mode**: Copies entities in batches with pauses and viewport refreshes. Use for videos where the drawing should visibly appear over time. Validate afterward; batch mode may create one or more extra dependent block references in some drawings.
- **Prepare-only pattern**: If a user wants the screen ready before drawing starts, create/open a blank target drawing first, wait for the user to say "start", then run batch mode with `--use-active-target`.

## AutoCAD Stability Notes

- If AutoCAD COM returns "call was rejected by callee" or document collections become unreadable, wait briefly and retry. If it persists, close extra AutoCAD windows and restart AutoCAD.
- Old DWGs may use legacy encodings and custom SHX fonts. Preserve source entities rather than recreating text by guessing.
- Do not overwrite the source DWG. Always write to a new output path.
- Use `--exact` for authoritative output even if a separate recorded batch version is created.

## Source Data Extraction

When exact entity copy is not acceptable and the user truly needs generated source code, extract structured data first:

- `DXFOUT`: export text DXF and inspect `TABLES`, `BLOCKS`, and `ENTITIES`.
- `DATAEXTRACTION`: export entity coordinates, radii, lengths, layers, and block attributes.
- `-LAYER ? *`: list layers, colors, linetypes, and lineweights.
- `-STYLE ? *`: list text styles and fonts.
- `-DIMSTYLE ? *`: list dimension style settings.
- `LIST`: inspect selected entity geometry.

Use `references/prompt-template.md` for a compact prompt template when generating AutoLISP or Python redraw code from extracted data.

## Bundled Script

Use `scripts/dwg_prompt_builder.py` to generate a drawing-specific prompt:

```powershell
python scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
```

Use `scripts/dwg_redraw.py` for deterministic AutoCAD COM redraw workflows:

```powershell
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_recorded.dwg --batch-size 22 --step-delay 0.45 --record
python scripts\dwg_redraw.py --source input.dwg --prepare-only
```

The script requires Windows, AutoCAD, Python 3.10+, and `pywin32`. Recording additionally uses `mss`, `imageio`, `imageio-ffmpeg`, and `numpy`.
