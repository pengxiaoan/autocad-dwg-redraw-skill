# Image Redraw Specification

This JSON format records what was reconstructed, where each value came from, and which facts remain uncertain. Version 2 is backward-compatible with the original `metadata`, `layers`, and `entities` structure.

## Contents

1. [Top-level structure](#top-level-structure)
2. [Evidence model](#evidence-model)
3. [Source and views](#source-and-views)
4. [Calibration](#calibration)
5. [Constraints](#constraints)
6. [Layers and entities](#layers-and-entities)
7. [Validation policy](#validation-policy)
8. [Compact example](#compact-example)

## Top-level structure

```json
{
  "schema_version": "2.0",
  "metadata": {
    "title": "Image-derived redraw",
    "units": "mm",
    "profile": "hybrid",
    "source_image": "input.jpg"
  },
  "source": {},
  "views": [],
  "calibration": [],
  "constraints": [],
  "layers": [],
  "entities": [],
  "validation": {}
}
```

Supported units are `unitless`, `mm`, `cm`, `m`, `in`, and `ft`. Use `unitless` when the image has no defensible physical scale.

Supported profiles are `strict-dimensioned`, `general`, `hybrid`, `visual-trace`, and `geometry-only`.

## Evidence model

Use these values consistently:

- `known`: directly stated by the user or legible in the source.
- `scaled`: measured after a documented calibration.
- `inferred`: derived from symmetry, continuity, layout, or engineering judgment.
- `unreadable`: visible but not reliably decipherable.

Important entities and constraints should include:

```json
{
  "evidence_level": "known",
  "source_refs": ["dimension-width-01"],
  "confidence": 0.98,
  "notes": "Readable 3000 dimension"
}
```

`confidence` is a review aid between 0 and 1; it does not replace evidence level.

## Source and views

The optional `source` block preserves input identity and interpretation notes:

```json
{
  "path": "input.jpg",
  "sha256": "...",
  "pixel_size": [960, 1081],
  "orientation_applied": 0,
  "perspective": "moderate",
  "occlusions": ["lower-right corner"],
  "notes": ["handwritten dimensions", "fold line crosses plan"]
}
```

Describe each independently scaled region in `views`:

```json
{
  "id": "plan-main",
  "name": "Main plan",
  "source_roi": [120, 80, 860, 980],
  "cad_origin": [0, 0],
  "scale_group": "plan-main",
  "rotation_degrees": 0
}
```

`source_roi` is `[left, top, right, bottom]` in image pixels. Do not assume all views share one scale group.

## Calibration

Record the transform evidence rather than only the final scale:

```json
{
  "id": "cal-main-x",
  "view_id": "plan-main",
  "method": "dimension-anchor",
  "source_points": [[243, 92], [562, 94]],
  "cad_points": [[0, 0], [3000, 0]],
  "value": 3000,
  "units": "mm",
  "evidence_level": "known",
  "source_refs": ["dimension-top-3000"]
}
```

Allowed methods include `dimension-anchor`, `affine`, `homography`, `sheet-scale`, and `visual-only`. A homography improves visual registration but does not by itself establish physical accuracy.

## Constraints

Constraints make the reconstruction testable. The bundled validator supports numeric `sum`, `difference`, and `equality` checks:

```json
{
  "id": "chain-bottom-width",
  "type": "sum",
  "terms": [3000, 1050, 1900],
  "expected": 5950,
  "absolute_tolerance": 1.0,
  "evidence_level": "known",
  "source_refs": ["dim-3000", "dim-1050", "dim-1900"]
}
```

For `difference`, the validator evaluates the first term minus the remaining terms. For `equality`, all terms must agree with `expected`. Keep geometric relationships such as tangency or concentricity as descriptive constraints until a domain-specific checker is available.

## Layers and entities

Recommended layers: `OBJECT`, `HIDDEN`, `CENTER`, `STRUCTURE`, `WINDOW`, `DOOR`, `DIM`, `TEXT`, `ASSUMPTION`, `TABLE`, `BORDER`, and `CONSTRUCTION`.

Every entity accepts optional `id`, `view_id`, `layer`, `color`, `linetype`, `evidence_level`, `source_refs`, `confidence`, and `notes`.

Supported entity types and required geometry fields:

| Type | Required fields |
|---|---|
| `line` | `start`, `end` |
| `polyline` | `points`; optional `closed` |
| `rectangle` | `p1` + `p2`, or `x` + `y` + `width` + `height` |
| `circle` | `center`, `radius` |
| `arc` | `center`, `radius`, `start_angle`, `end_angle` in degrees |
| `center_mark` | `center`; optional `size` |
| `text` | `text`, `point`; optional `height`, `rotation` |
| `mtext` | `text`, `point`, `width` |
| `leader` | `points`, `text` |
| `linear_dimension` | `p1`, `p2`, `dimline`; optional `angle`, `text` |
| `aligned_dimension` | `p1`, `p2`, `dimline`; optional `text` |
| `radial_dimension` | `center`, `chord`; optional `leader`, `text` |
| `table` | `origin`, `col_widths`, `row_heights`, `cells` |

Coordinates are CAD coordinates, not pixels. Angles are degrees in the spec and converted to radians by the AutoCAD renderer.

For unreadable text, use `[UNREADABLE]`, set `evidence_level` to `unreadable`, and preserve its source location.

## Validation policy

The optional block declares acceptance requirements:

```json
{
  "required_layers": ["OBJECT", "DIM"],
  "forbidden_entity_types": [],
  "required_view_ids": ["plan-main"],
  "constraint_tolerance": 1.0,
  "visual_metrics_are_advisory": true
}
```

For geometry-only output, list annotation types under `forbidden_entity_types`, or invoke the renderer and inspector with `--geometry-only`.

## Compact example

```json
{
  "schema_version": "2.0",
  "metadata": {
    "title": "Bracket from photo",
    "units": "mm",
    "profile": "hybrid",
    "source_image": "bracket.jpg"
  },
  "views": [
    {"id": "front", "source_roi": [40, 30, 920, 700], "cad_origin": [0, 0], "scale_group": "front"}
  ],
  "calibration": [
    {
      "id": "width-anchor",
      "view_id": "front",
      "method": "dimension-anchor",
      "source_points": [[100, 600], [800, 600]],
      "cad_points": [[0, 0], [100, 0]],
      "value": 100,
      "units": "mm",
      "evidence_level": "known"
    }
  ],
  "layers": [
    {"name": "OBJECT", "color": 7, "linetype": "Continuous"},
    {"name": "ASSUMPTION", "color": 1, "linetype": "Continuous"}
  ],
  "entities": [
    {
      "id": "outer",
      "view_id": "front",
      "type": "rectangle",
      "layer": "OBJECT",
      "p1": [0, 0],
      "p2": [100, 60],
      "evidence_level": "scaled",
      "source_refs": ["width-anchor"]
    },
    {
      "id": "hole-1",
      "view_id": "front",
      "type": "circle",
      "layer": "ASSUMPTION",
      "center": [50, 30],
      "radius": 8,
      "evidence_level": "inferred",
      "confidence": 0.65
    }
  ],
  "validation": {
    "required_layers": ["OBJECT"],
    "visual_metrics_are_advisory": true
  }
}
```
