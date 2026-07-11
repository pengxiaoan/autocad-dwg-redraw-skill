# Image-to-DWG Validation

Validation is a chain of evidence. A visually convincing overlay can still have the wrong scale; a dimensionally correct model can look different because the photo has perspective distortion.

## Contents

1. [Acceptance profiles](#acceptance-profiles)
2. [Input gate](#input-gate)
3. [Specification checks](#specification-checks)
4. [CAD output checks](#cad-output-checks)
5. [Visual comparison](#visual-comparison)
6. [Decision rules](#decision-rules)
7. [Report contract](#report-contract)

## Acceptance profiles

| Profile | Physical units required | Calibration required | Visual comparison | Annotations |
|---|---:|---:|---:|---|
| `strict-dimensioned` | yes | known/scaled anchor per view | required | per source/requirements |
| `general` | recommended | when accuracy is claimed | required | per requirements |
| `hybrid` | yes for dimensioned regions | per dimensioned view | required | allowed |
| `visual-trace` | no | registration anchors only | required | traced or omitted |
| `geometry-only` | depends on accuracy claim | depends on accuracy claim | required | must be omitted |

Select the profile before drawing. Changing the profile changes acceptance criteria and must be recorded.

## Input gate

Always check:

- file is readable and its hash is recorded;
- EXIF orientation is known or normalized;
- relevant geometry is not cropped;
- image resolution supports the requested detail;
- blur and contrast are reported, not guessed away;
- perspective, fold lines, glare, occlusion, and background clutter are noted;
- units and dimension anchors are identified;
- each independently scaled view or region has its own calibration group;
- OCR text is attached to a visible feature before it becomes an engineering value.

Block `strict-dimensioned` when no reliable units or scale anchors exist. Return `needs_review` when dimension strings conflict, endpoints are ambiguous, or perspective correction changes the interpretation materially.

The bundled preflight quality metrics are heuristics. Scanner images, line drawings, and phone photos have different blur and contrast behavior, so thresholds are warnings rather than universal truth.

## Specification checks

Validate before launching AutoCAD:

- supported schema, profile, units, layers, and entity types;
- finite coordinates and positive radii/widths/heights;
- sufficient polyline, leader, and table data;
- unique IDs and valid `view_id` references;
- evidence levels and confidence ranges;
- calibration point counts and matching source/CAD arrays;
- known dimension chains and numeric constraints within tolerance;
- no `unreadable` value used as a solved dimension;
- geometry-only requirements reflected in omit policy.

Dimension authority is: explicit user correction, explicit readable source dimension, derived exact constraint, calibrated measurement, inferred estimate. Keep both values and flag a conflict when two facts at the same authority disagree beyond tolerance.

## CAD output checks

Check the actual deliverable, not just the drawing script:

- DWG opens in AutoCAD and is not an empty or recovery-only document;
- insertion units agree with the spec;
- ModelSpace/PaperSpace choice is intentional;
- required layers exist and contain plausible entities;
- entity classes match the selected profile;
- geometry-only DWG contains no text, dimensions, leaders, or table text;
- dimensions are associative/editable where required;
- Chinese or other non-Latin text displays without replacement glyphs;
- no object is unexpectedly far from the main extents;
- DXF export passes an `ezdxf` audit;
- preview is rendered to a fixed page, not an unbounded pixel canvas based on millimeter extents.

Counts are useful regression signals, not proof of correctness. A rectangle can become one polyline or four lines and still be semantically equivalent.

## Visual comparison

Register the CAD preview to the source with at least four well-distributed corresponding points. For perspective photographs, use a homography per planar view. Do not combine unrelated views under one transform.

Review:

- side-by-side overview;
- semi-transparent registered overlay;
- edge-only difference image;
- missing-source and extra-CAD edge masks;
- CAD-edge distance to nearest source edge: median and 95th percentile;
- percentage of CAD edges within configurable pixel distances;
- source-edge coverage by CAD edges.

Prefer edge/skeleton distances over raw RGB difference because paper color, shadows, compression, annotations, and scan noise are not CAD geometry. Default pixel thresholds should be scaled to output resolution and treated as advisory.

Visual comparison can detect omission, displacement, topology, and view-layout errors. It cannot prove real-world size, units, tolerances, material, or design intent.

## Decision rules

- `pass`: all mandatory profile checks pass and no unresolved authoritative conflict remains.
- `pass_with_warnings`: only noncritical uncertainty remains; it is enumerated in the manifest.
- `needs_review`: human interpretation is needed, but useful work can continue.
- `blocked`: the chosen profile requires missing evidence, such as units or an anchor.
- `fail`: corrupt output, invalid spec, failed mandatory constraint, or prohibited entities.

Never lower the profile merely to make validation pass without recording the change.

## Report contract

Each JSON report should include:

```json
{
  "tool": "validator name and version",
  "timestamp_utc": "ISO-8601",
  "inputs": [{"path": "...", "sha256": "..."}],
  "profile": "general",
  "status": "pass_with_warnings",
  "checks": [],
  "metrics": {},
  "warnings": [],
  "blockers": [],
  "assumptions": [],
  "next_actions": []
}
```

The final manifest should link all reports and identify the exact DWG, DXF, spec, source image, previews, hashes, units, profile, unresolved assumptions, and disposition.
