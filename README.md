# AutoCAD DWG Redraw Skill

This repository contains a Codex skill for generating standardized DWG redraw prompts, rebuilding DWGs, validating entity counts, and recording AutoCAD redraw demos.

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
Use $autocad-dwg-redraw. I will provide a DWG; generate a custom redraw prompt, then rebuild it exactly and create a recorded redraw demo.
```

The skill includes:

- A standard workflow for turning any source DWG into a custom redraw prompt.
- A workflow for exact DWG reconstruction through AutoCAD COM.
- A video-friendly batch redraw workflow.
- A reusable prompt builder at `skills/autocad-dwg-redraw/scripts/dwg_prompt_builder.py`.
- A reusable script at `skills/autocad-dwg-redraw/scripts/dwg_redraw.py`.
- A prompt template for generated AutoLISP/Python redraw programs.

## Script Examples

Generate a drawing-specific custom redraw prompt:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md
```

If AutoCAD is stuck on the Start page or COM document access fails, restart AutoCAD cleanly:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_prompt_builder.py --source input.dwg --output input-redraw-prompt.md --restart-autocad --acad-exe "C:\Path\To\acad.exe"
```

Final accurate redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
```

Clean AutoCAD restart plus exact redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact --restart-autocad --acad-exe "C:\Path\To\acad.exe"
```

Recorded redraw demo:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_demo.dwg --batch-size 22 --step-delay 0.45 --record
```

Prepare a blank target first, then start later:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --prepare-only
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_demo.dwg --use-active-target --record
```

No personal DWG files, recordings, or local machine paths are included in this repository.

## Standard Process

1. Provide a source `.dwg`.
2. Generate `*-redraw-prompt.md` with `dwg_prompt_builder.py`.
3. Review the prompt's drawing fingerprint: entity count, layers, blocks, text styles, dimension styles, and object distribution.
4. Run `dwg_redraw.py --exact` for the final deliverable.
5. Run `dwg_redraw.py --record` for the visible video demo.
6. Treat the exact redraw as the authoritative output; use the recorded redraw only as video material if batch mode creates extra dependent blocks.

## External Recorder Workflow

For production recording, start a third-party recorder first, confirm it is recording, then run the redraw command. Keep the skill's built-in `--record` for lightweight automated MP4 capture.
