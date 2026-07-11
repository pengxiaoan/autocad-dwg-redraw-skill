#!/usr/bin/env python
"""Read-only structural inspection of a DWG through AutoCAD COM."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ANNOTATION_CLASSES = {"AcDbText", "AcDbMText", "AcDbLeader", "AcDbMLeader", "AcDbDimension", "AcDbTable"}
INSUNITS = {0: "unitless", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}


def retry(action, attempts: int = 60, delay: float = 0.5):
    last_error = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def find_or_open_document(client, dwg: Path):
    try:
        app = client.GetActiveObject("AutoCAD.Application")
    except Exception:
        app = client.Dispatch("AutoCAD.Application")
    target = str(dwg).lower()
    try:
        count = retry(lambda: app.Documents.Count)
        for index in range(count):
            candidate = retry(lambda idx=index: app.Documents.Item(idx))
            if str(retry(lambda: candidate.FullName) or "").lower() == target:
                retry(lambda: candidate.ModelSpace.Count)
                return candidate, False
    except Exception:
        pass
    retry(lambda: app.Documents.Open(str(dwg)), attempts=10, delay=1.0)
    document = retry(lambda: app.ActiveDocument)
    retry(lambda: document.ModelSpace.Count)
    return document, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a DWG without modifying it.")
    parser.add_argument("--dwg", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--expected-units", choices=sorted(set(INSUNITS.values())))
    parser.add_argument("--required-layers", default="")
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--close", action="store_true", help="Close the DWG after inspection. Default leaves it open to avoid closing a user's existing document.")
    args = parser.parse_args()
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise SystemExit("pywin32 is required for DWG inspection.") from exc
    pythoncom.CoInitialize()
    dwg = Path(args.dwg).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    doc, opened_by_script = find_or_open_document(win32com.client, dwg)
    try:
        counts = Counter()
        layers = Counter()
        modelspace = retry(lambda: doc.ModelSpace)
        total = int(retry(lambda: modelspace.Count))
        for index in range(total):
            entity = retry(lambda idx=index: modelspace.Item(idx))
            object_name = str(retry(lambda: entity.ObjectName))
            counts[object_name] += 1
            try:
                layers[str(retry(lambda: entity.Layer))] += 1
            except Exception:
                layers["<unreadable>"] += 1
        unit_code = int(retry(lambda: doc.GetVariable("INSUNITS")))
        units = INSUNITS.get(unit_code, f"code-{unit_code}")
        if not counts:
            errors.append("ModelSpace is empty.")
        if args.expected_units and units != args.expected_units:
            errors.append(f"DWG units are {units}, expected {args.expected_units}.")
        required = {v.strip() for v in args.required_layers.split(",") if v.strip()}
        missing = sorted(required - set(layers))
        if missing:
            errors.append(f"Required layers have no ModelSpace entities: {', '.join(missing)}")
        annotations = sum(value for key, value in counts.items() if key in ANNOTATION_CLASSES or "Dimension" in key)
        if args.geometry_only and annotations:
            errors.append(f"Geometry-only output contains {annotations} annotation object(s).")
        status = "fail" if errors else ("pass_with_warnings" if warnings else "pass")
        report = {
            "tool": "inspect_dwg_output/1.0", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "inputs": [{"path": str(dwg)}], "status": status,
            "metrics": {"modelspace_total": sum(counts.values()), "entity_counts": counts, "layer_counts": layers, "insunits_code": unit_code, "units": units, "annotation_objects": annotations},
            "warnings": warnings, "blockers": errors,
        }
    finally:
        if args.close and opened_by_script:
            try:
                doc.Close(False)
            except Exception:
                pass
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "status": report["status"]}, indent=2))
    return 3 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
