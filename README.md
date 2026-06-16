# AutoCAD DWG Redraw Skill

This repository contains a Codex skill for generating standardized DWG redraw prompts, rebuilding DWGs through AutoCAD COM, and validating entity, annotation, layer, block, and layout fidelity.

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

## Use

Ask Codex:

```text
Use $autocad-dwg-redraw. I will provide a DWG; generate a custom redraw prompt, then rebuild and validate it.
```

The skill includes:

- A standard workflow for turning any source DWG into a custom redraw prompt.
- A workflow for exact DWG reconstruction through AutoCAD COM.
- Validation for entity counts, object type distribution, dimensions, leaders, annotations, layers, blocks, and PaperSpace.
- A reusable prompt builder at `skills/autocad-dwg-redraw/scripts/dwg_prompt_builder.py`.
- A reusable redraw script at `skills/autocad-dwg-redraw/scripts/dwg_redraw.py`.
- A prompt template for generated AutoLISP/Python redraw programs when exact extracted entity data is available.

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

## Standard Process

1. Provide a source `.dwg`.
2. Generate `*-redraw-prompt.md` with `dwg_prompt_builder.py`.
3. Review the prompt's drawing fingerprint: entity count, layers, blocks, text styles, dimension styles, annotation counts, and object distribution.
4. Run `dwg_redraw.py` for the final deliverable.
5. Validate that the target has the same ModelSpace/PaperSpace entity counts, dimensions/leaders, annotations, and object type distribution as the source.

## Notes

- AutoCAD must be installed on Windows.
- Python requires `pywin32`.
- For legacy DWGs, custom objects, proxy objects, xrefs, or annotative dimensions, run a visual review in AutoCAD after automated validation.
