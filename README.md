# AutoCAD Redraw Skills

This repository contains two Codex skills:

- `autocad-dwg-redraw`: exact, evidence-backed reconstruction when a source or intermediate DWG exists.
- `autocad-image-redraw`: generalized raster image to DWG/DXF reconstruction with input preflight, evidence-aware specs, CAD output inspection, visual comparison, and iterative validation.

## Install

Install the skill from this repository:

```powershell
python %USERPROFILE%\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo <owner>/<repo> --path skills/autocad-dwg-redraw
```

Or with a GitHub URL:

```powershell
python %USERPROFILE%\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --url https://github.com/<owner>/<repo>/tree/main/skills/autocad-dwg-redraw
```

Restart Codex after installation.

Install the image-to-DWG skill:

```powershell
python %USERPROFILE%\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo pengxiaoan/autocad-dwg-redraw-skill --path skills/autocad-image-redraw
```

## Use

Ask Codex:

```text
Use $autocad-dwg-redraw. I will provide a DWG; generate a custom redraw prompt, then rebuild and validate it.
```

For a photographed drawing, scan, sketch, screenshot, PNG, or JPG:

```text
Use $autocad-image-redraw. Preflight this image, create and validate an evidence-aware CAD spec, draw an editable DWG/DXF, inspect it, compare it with the source image, and report unresolved assumptions.
```

The skill includes:

- A standard workflow for turning any source DWG into a custom redraw prompt.
- A PDF-derived DWG workflow for cases where a PDF is available but the original DWG is not.
- A workflow for exact DWG reconstruction through AutoCAD COM.
- Validation for entity counts, object type distribution, dimensions, leaders, annotations, layers, blocks, and PaperSpace.
- A reusable prompt builder at `skills/autocad-dwg-redraw/scripts/dwg_prompt_builder.py`.
- A reusable redraw script at `skills/autocad-dwg-redraw/scripts/dwg_redraw.py`.
- A prompt template for generated AutoLISP/Python redraw programs when exact extracted entity data is available.
- Raster input quality checks and explicit `known` / `scaled` / `inferred` / `unreadable` evidence levels.
- Dimension-driven, hybrid, visual-trace, and geometry-only image redraw profiles.
- Spec validation, AutoCAD DWG inspection, fixed-page DXF preview, registered overlay, and edge-distance comparison.
- A validation contract that separates visual similarity from physical dimensional accuracy.

## Script Examples

Generate a drawing-specific custom redraw prompt:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
```

If AutoCAD is stuck on the Start page or COM document access fails, restart AutoCAD cleanly:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md --restart-autocad --acad-exe "C:\Path\To\acad.exe"
```

Create the validated redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg
```

Clean AutoCAD restart plus redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --restart-autocad --acad-exe "C:\Path\To\acad.exe"
```

ModelSpace-only redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_modelspace_only.dwg --modelspace-only
```

No personal DWG files or local machine paths are included in this repository.

Image-redraw preflight and validation:

```powershell
python skills\autocad-image-redraw\scripts\preflight_image_redraw.py --image input.jpg --mode general --output reports\input-preflight.json
python skills\autocad-image-redraw\scripts\validate_image_redraw_spec.py --spec redraw-spec.json --profile general --report reports\spec-validation.json
python skills\autocad-image-redraw\scripts\draw_image_spec.py --spec redraw-spec.json --output outputs\redraw.dwg
python skills\autocad-image-redraw\scripts\inspect_dwg_output.py --dwg outputs\redraw.dwg --report reports\dwg-inspection.json
python skills\autocad-image-redraw\scripts\render_dxf_preview.py --dxf outputs\redraw.dxf --png reports\preview.png --pdf reports\preview.pdf
python skills\autocad-image-redraw\scripts\compare_redraw.py --source input.jpg --cad-preview reports\preview.png --anchors anchors.json --output-dir reports\comparison
```

## Standard Process

1. Provide a source `.dwg`, or convert a PDF into an auditable intermediate `.dwg`.
2. Generate `*-redraw-prompt.md` with `dwg_prompt_builder.py`.
3. Review the prompt's drawing fingerprint: entity count, layers, blocks, text styles, dimension styles, annotation counts, and object distribution.
4. Run `dwg_redraw.py` for the final deliverable.
5. Validate that the target has the same ModelSpace/PaperSpace entity counts, dimensions/leaders, annotations, and object type distribution as the source or intermediate DWG.

## Notes

- AutoCAD must be installed on Windows.
- Python requires `pywin32`.
- PDF-derived DWGs should be reported as PDF-derived, not as exact copies of an unavailable original DWG.
- For legacy DWGs, custom objects, proxy objects, xrefs, or annotative dimensions, run a visual review in AutoCAD after automated validation.
- Image-derived drawings must not be described as dimensionally exact unless units and sufficient authoritative constraints are present and validated.
