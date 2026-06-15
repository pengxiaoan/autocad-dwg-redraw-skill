# AutoCAD DWG Redraw Skill

This repository contains a Codex skill for rebuilding, validating, and recording AutoCAD DWG redraw workflows.

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
Use $autocad-dwg-redraw to rebuild this DWG exactly and create a recorded redraw demo.
```

The skill includes:

- A workflow for exact DWG reconstruction through AutoCAD COM.
- A video-friendly batch redraw workflow.
- A reusable script at `skills/autocad-dwg-redraw/scripts/dwg_redraw.py`.
- A prompt template for generated AutoLISP/Python redraw programs.

## Script Examples

Final accurate redraw:

```powershell
python skills\autocad-dwg-redraw\scripts\dwg_redraw.py --source input.dwg --output outputs\redraw_exact.dwg --exact
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
