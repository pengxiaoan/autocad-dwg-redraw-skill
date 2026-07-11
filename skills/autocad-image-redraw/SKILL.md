---
name: autocad-image-redraw
description: Convert raster drawing references—including screenshots, scans, photos, sketches, exported PNG/JPG files, and photographed plans—into structured, editable AutoCAD DWG/DXF drawings with explicit evidence tracking, input preflight, specification validation, output inspection, and visual comparison. Use for dimension-driven redraws, hybrid reconstruction, visual tracing, or geometry-only redraws when the source is an image rather than a trustworthy source DWG.
---

# AutoCAD Image Redraw

Reconstruct an image as an auditable CAD drawing. Treat the image as evidence, not as ground truth. If a trustworthy source DWG exists, use `autocad-dwg-redraw` instead.

## Non-Negotiable Rules

1. Never claim physical accuracy from pixel similarity alone.
2. Resolve geometry in this order: explicit user requirements, readable dimensions, derived constraints, calibrated image measurements, then clearly labeled visual estimates.
3. Track every important value as `known`, `scaled`, `inferred`, or `unreadable`.
4. Calibrate each view or region independently when perspective or differing view scales are present.
5. Do not silently choose between conflicting dimensions. Record the conflict and return `needs_review` or `blocked`.
6. Preserve the original image, specs, reports, previews, and hashes so the result can be reproduced.

## Choose a Profile

- `strict-dimensioned`: engineering deliverable; requires readable units and enough known or calibrated anchors to constrain the geometry.
- `general`: balanced default for plans, sketches, screenshots, and mixed-quality references.
- `hybrid`: use dimensions where available and calibrated proportions elsewhere; label inferred geometry.
- `visual-trace`: reproduce visible linework without asserting real-world scale.
- `geometry-only`: retain object geometry and useful construction layers; omit dimensions, leaders, notes, and table text.

If the source lacks a unit or scale anchor, choose `visual-trace` or use `unitless`. Do not default to millimeters merely because the drawing looks technical.

## Runtime Requirements

Use Windows with AutoCAD and `pywin32` for DWG generation/inspection. Preflight and comparison require Pillow, NumPy, and OpenCV; DXF preview requires `ezdxf` and PyMuPDF:

```powershell
python -m pip install pywin32 pillow numpy opencv-python ezdxf pymupdf
```

## End-to-End Workflow

### 1. Preserve and preflight the source

Copy the source into the project, compute a hash, and inspect readability before interpreting it:

```powershell
python scripts\preflight_image_redraw.py --image input.jpg --mode general --output reports\input-preflight.json
```

Review rotation, crop, resolution, contrast, blur, perspective, occlusion, visible units, and available scale anchors. A quality warning is not automatically a blocker; it becomes a blocker when the selected profile requires evidence the image cannot provide.

### 2. Build a semantic redraw spec

Use `references/image-redraw-spec.md`. Create stable entity IDs, identify each view, record calibration anchors and evidence, and encode constraints rather than relying on raw pixel coordinates.

Keep source and CAD coordinate systems separate:

- source coordinates: image pixels, origin at top-left;
- CAD coordinates: drawing units, origin chosen for auditability;
- calibration: a view-specific affine, homography, or dimension-based relationship between them.

### 3. Validate the spec before drawing

```powershell
python scripts\validate_image_redraw_spec.py --spec redraw-spec.json --profile general --report reports\spec-validation.json
```

Resolve errors, impossible geometry, duplicate IDs, missing required fields, invalid units, and constraint failures. In `strict-dimensioned`, missing units or calibration evidence must block drawing.

### 4. Draw in AutoCAD

```powershell
python scripts\draw_image_spec.py --spec redraw-spec.json --output outputs\redraw.dwg
```

For Chinese text:

```powershell
python scripts\draw_image_spec.py --spec redraw-spec.json --output outputs\redraw.dwg --text-style CN_TEXT --text-font "C:\Windows\Fonts\simhei.ttf"
```

For geometry-only output:

```powershell
python scripts\draw_image_spec.py --spec redraw-spec.json --output outputs\redraw-geometry.dwg --geometry-only
```

When multiple AutoCAD instances or the Start page confuse COM, use `--attach-document` with a readable DWG. Use `--dry-run` before connecting to AutoCAD.

For rough, open-source visual tracing without AutoCAD, use `image_to_dxf_open_source.py`. For vector PDFs, use `pdf_vector_to_dxf.py` before raster tracing. Neither path converts uncertain pixels into authoritative dimensions.

### 5. Inspect the CAD output

```powershell
python scripts\inspect_dwg_output.py --dwg outputs\redraw.dwg --report reports\dwg-inspection.json
```

Verify the file opens, ModelSpace is nonempty, units match the spec, expected layers and entity classes exist, and forbidden annotation classes are absent in geometry-only mode. Export an auditable DXF from AutoCAD, then audit and render it:

```powershell
python scripts\render_dxf_preview.py --dxf outputs\redraw.dxf --png reports\cad-preview.png --pdf reports\cad-preview.pdf
```

### 6. Compare against the source

Create an anchors JSON containing corresponding source-image and CAD-preview points, then run:

```powershell
python scripts\compare_redraw.py --source input.jpg --cad-preview reports\cad-preview.png --anchors anchors.json --output-dir reports\comparison
```

Inspect the side-by-side image, registered overlay, difference view, edge coverage, and edge-distance statistics. Use the comparison to find omitted walls, shifted holes, incorrect arcs, text collisions, and view-layout errors. Do not use it to validate physical dimensions.

### 7. Iterate and issue a disposition

Fix the highest-impact failure, regenerate, and rerun validation. Finish with one status:

- `pass`: selected profile and all required checks passed;
- `pass_with_warnings`: deliverable is usable with documented noncritical uncertainty;
- `needs_review`: a human decision is required, usually due to conflicting or inferred evidence;
- `blocked`: required source evidence is missing;
- `fail`: output is corrupt or violates a mandatory check.

## Delivery Contract

Deliver as applicable:

- editable DWG and audit DXF;
- redraw spec JSON and calibration/anchor JSON;
- input preflight, spec validation, and DWG inspection reports;
- fixed-page PNG/PDF preview;
- side-by-side, overlay, difference image, and metrics JSON;
- manifest containing source/output hashes, selected profile, units, assumptions, warnings, and final status.

## References and Scripts

- `references/image-redraw-spec.md`: generalized spec, evidence, views, calibration, constraints, and entities.
- `references/image-redraw-validation.md`: acceptance policies, checks, metrics, statuses, and report contract.
- `scripts/preflight_image_redraw.py`: source-image quality and evidence gate.
- `scripts/validate_image_redraw_spec.py`: semantic and constraint validation.
- `scripts/draw_image_spec.py`: JSON-to-DWG AutoCAD renderer.
- `scripts/inspect_dwg_output.py`: read-only DWG structure inspection through AutoCAD COM.
- `scripts/render_dxf_preview.py`: DXF audit and deterministic fixed-page preview.
- `scripts/compare_redraw.py`: registered visual comparison and edge metrics.
- `scripts/image_to_dxf_open_source.py`: rough raster-to-DXF baseline.
- `scripts/pdf_vector_to_dxf.py`: vector-PDF extraction path.
