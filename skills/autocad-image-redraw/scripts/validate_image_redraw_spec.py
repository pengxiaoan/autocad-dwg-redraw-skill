#!/usr/bin/env python
"""Validate generalized image-redraw JSON before launching AutoCAD."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILES = {"strict-dimensioned", "general", "hybrid", "visual-trace", "geometry-only"}
UNITS = {"unitless", "mm", "cm", "m", "in", "ft"}
EVIDENCE = {"known", "scaled", "inferred", "unreadable"}
REQUIRED = {
    "line": ["start", "end"], "polyline": ["points"], "rectangle": [],
    "circle": ["center", "radius"], "arc": ["center", "radius", "start_angle", "end_angle"],
    "text": ["text", "point"], "mtext": ["text", "point", "width"],
    "leader": ["points", "text"], "linear_dimension": ["p1", "p2", "dimline"],
    "aligned_dimension": ["p1", "p2", "dimline"], "radial_dimension": ["center", "chord"],
    "table": ["origin", "col_widths", "row_heights", "cells"], "center_mark": ["center"],
}


def finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite(item) for item in value)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an image-redraw spec.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES))
    args = parser.parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        spec = {}
        errors.append(f"Cannot load JSON spec: {exc}")
    if not isinstance(spec, dict):
        errors.append("Spec root must be an object.")
        spec = {}

    metadata = spec.get("metadata", {}) if isinstance(spec.get("metadata", {}), dict) else {}
    profile = args.profile or metadata.get("profile", "general")
    units = metadata.get("units", "unitless")
    if profile not in PROFILES:
        errors.append(f"Unsupported profile: {profile}")
    if units not in UNITS:
        errors.append(f"Unsupported units: {units}")
    entities = spec.get("entities", [])
    if not isinstance(entities, list):
        errors.append("entities must be an array.")
        entities = []
    if not entities:
        errors.append("entities is empty.")

    view_ids = {v.get("id") for v in spec.get("views", []) if isinstance(v, dict) and v.get("id")}
    entity_ids: set[str] = set()
    counts = Counter()
    for index, entity in enumerate(entities, 1):
        if not isinstance(entity, dict):
            errors.append(f"Entity #{index} is not an object.")
            continue
        etype = entity.get("type")
        counts[str(etype)] += 1
        if etype not in REQUIRED:
            errors.append(f"Entity #{index} has unsupported type: {etype}")
            continue
        missing = [field for field in REQUIRED[etype] if field not in entity]
        if etype == "rectangle" and not (("p1" in entity and "p2" in entity) or all(k in entity for k in ("x", "y", "width", "height"))):
            missing.append("p1+p2 or x+y+width+height")
        if missing:
            errors.append(f"Entity #{index} ({etype}) missing: {', '.join(missing)}")
        if not finite(entity):
            errors.append(f"Entity #{index} contains NaN or infinite numeric values.")
        if etype in {"circle", "arc"} and float(entity.get("radius", 0) or 0) <= 0:
            errors.append(f"Entity #{index} radius must be positive.")
        if etype == "polyline" and len(entity.get("points", [])) < 2:
            errors.append(f"Entity #{index} polyline requires at least two points.")
        eid = entity.get("id")
        if eid:
            if eid in entity_ids:
                errors.append(f"Duplicate entity id: {eid}")
            entity_ids.add(eid)
        evidence = entity.get("evidence_level")
        if evidence is not None and evidence not in EVIDENCE:
            errors.append(f"Entity #{index} has invalid evidence_level: {evidence}")
        confidence = entity.get("confidence")
        if confidence is not None and not 0 <= float(confidence) <= 1:
            errors.append(f"Entity #{index} confidence must be between 0 and 1.")
        if entity.get("view_id") and entity["view_id"] not in view_ids:
            errors.append(f"Entity #{index} references unknown view_id: {entity['view_id']}")

    calibrations = spec.get("calibration", [])
    if not isinstance(calibrations, list):
        errors.append("calibration must be an array.")
        calibrations = []
    usable_calibrations = 0
    for index, cal in enumerate(calibrations, 1):
        if not isinstance(cal, dict):
            errors.append(f"Calibration #{index} is not an object.")
            continue
        src, cad = cal.get("source_points", []), cal.get("cad_points", [])
        if src or cad:
            if not isinstance(src, list) or not isinstance(cad, list) or len(src) != len(cad) or len(src) < 2:
                errors.append(f"Calibration #{index} needs matching source_points/cad_points with at least two pairs.")
        if cal.get("evidence_level") in {"known", "scaled"} and (cal.get("value") is not None or len(src) >= 2):
            usable_calibrations += 1

    constraint_results = []
    for index, constraint in enumerate(spec.get("constraints", []), 1):
        if not isinstance(constraint, dict):
            errors.append(f"Constraint #{index} is not an object.")
            continue
        ctype = constraint.get("type")
        if ctype not in {"sum", "difference", "equality"}:
            warnings.append(f"Constraint #{index} type '{ctype}' is descriptive and was not numerically checked.")
            continue
        try:
            terms = [float(v) for v in constraint["terms"]]
            expected = float(constraint["expected"])
            tolerance = float(constraint.get("absolute_tolerance", spec.get("validation", {}).get("constraint_tolerance", 1e-6)))
            if ctype == "sum":
                actual = sum(terms)
            elif ctype == "difference":
                actual = terms[0] - sum(terms[1:])
            else:
                actual = max(terms, key=lambda value: abs(value - expected))
            passed = bool(terms) and abs(actual - expected) <= tolerance and (ctype != "equality" or all(abs(value - expected) <= tolerance for value in terms))
            constraint_results.append({"id": constraint.get("id", index), "type": ctype, "actual": actual, "expected": expected, "tolerance": tolerance, "passed": passed})
            if not passed:
                errors.append(f"Constraint {constraint.get('id', index)} failed: {actual} vs {expected} ± {tolerance}.")
        except Exception as exc:
            errors.append(f"Constraint #{index} is invalid: {exc}")

    if profile == "strict-dimensioned":
        if units == "unitless":
            errors.append("strict-dimensioned profile cannot use unitless units.")
        if usable_calibrations == 0:
            errors.append("strict-dimensioned profile requires a known/scaled calibration anchor.")
    if profile == "geometry-only" and any(t in counts for t in ("text", "mtext", "leader", "linear_dimension", "aligned_dimension", "radial_dimension")):
        warnings.append("Spec contains annotations; render and inspect with --geometry-only.")
    if not spec.get("schema_version"):
        warnings.append("Legacy spec has no schema_version; interpreted as backward-compatible version 1.")

    checks.extend([
        {"name": "profile", "passed": profile in PROFILES, "value": profile},
        {"name": "units", "passed": units in UNITS, "value": units},
        {"name": "entities_nonempty", "passed": bool(entities), "value": len(entities)},
        {"name": "numeric_constraints", "passed": all(c["passed"] for c in constraint_results), "results": constraint_results},
    ])
    status = "fail" if errors else ("pass_with_warnings" if warnings else "pass")
    report = {
        "tool": "validate_image_redraw_spec/1.0", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": [{"path": str(spec_path)}], "profile": profile, "status": status, "checks": checks,
        "metrics": {"units": units, "entity_total": len(entities), "entity_counts": counts, "view_count": len(view_ids), "usable_calibrations": usable_calibrations},
        "warnings": warnings, "blockers": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "status": status, "errors": len(errors), "warnings": len(warnings)}, indent=2))
    return 3 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
