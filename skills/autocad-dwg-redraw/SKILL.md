---
name: autocad-dwg-redraw
description: Rebuild, validate, and screen-record AutoCAD DWG drawings using AutoCAD COM automation. Use when Codex needs to reproduce a source .dwg as a new DWG, extract drawing metadata, compare ModelSpace entity counts, create video-friendly redraw demos, or guide users through DWG-to-DXF/DATAEXTRACTION workflows for precise AutoCAD reconstruction.
---

# AutoCAD DWG Redraw

Use this skill to reproduce an existing AutoCAD drawing as a new DWG and, when needed, record the redraw process for demonstrations.

## Core Rule

Do not infer a complex DWG from screenshots or visual style alone when the source DWG is available. First extract or copy actual source entities, then validate against the original.

For final delivery, prefer exact entity copy. For videos, use batch redraw with delays, then clearly label it as a demonstration copy.

## Workflow

1. Confirm AutoCAD is installed and can open the source DWG.
2. Inspect the prompt/reference file if provided. Pay attention to required layers, blocks, title blocks, BOM tables, linetypes, text styles, dimensions, and encoding notes.
3. Open the source DWG in AutoCAD or let the script open it.
4. Generate a final accurate DWG with exact mode:
   ```powershell
   python path\to\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
   ```
5. Validate at minimum:
   - Source ModelSpace entity count equals target ModelSpace entity count.
   - PaperSpace count is expected.
   - AutoCAD `ZOOM EXTENTS` shows the full drawing.
   - Title block, BOM, dimensions, text, and block inserts visually match.
6. For screen-recorded demos, use batch mode:
   ```powershell
   python path\to\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_recorded.dwg --batch-size 22 --step-delay 0.45 --record
   ```

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

Use `scripts/dwg_redraw.py` for deterministic AutoCAD COM workflows:

```powershell
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
python scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_recorded.dwg --batch-size 22 --step-delay 0.45 --record
python scripts\dwg_redraw.py --source input.dwg --prepare-only
```

The script requires Windows, AutoCAD, Python 3.10+, and `pywin32`. Recording additionally uses `mss`, `imageio`, `imageio-ffmpeg`, and `numpy`.
