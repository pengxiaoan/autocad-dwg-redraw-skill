"""Rebuild a source DWG into a new DWG using AutoCAD COM automation.

Example:
    python dwg_redraw.py --source input.dwg --output outputs/redraw_exact.dwg --restart-autocad --acad-exe "C:\\Path\\To\\acad.exe"
"""

from __future__ import annotations

import argparse
import collections
import subprocess
import time
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT


ANNOTATION_TYPES = (
    "Dimension",
    "Leader",
    "Text",
    "MText",
    "Tolerance",
)


def com_retry(action, attempts: int = 30, delay: float = 0.4):
    last_error = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def connect_autocad():
    pythoncom.CoInitialize()
    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        print("Connected to running AutoCAD.")
    except Exception:
        acad = win32com.client.Dispatch("AutoCAD.Application")
        print("Started AutoCAD.")
    try:
        acad.Visible = True
    except Exception as exc:
        print(f"Warning: could not set AutoCAD visible: {exc}")
    try:
        acad.WindowState = 3
    except Exception:
        pass
    return acad


def restart_autocad(acad_exe: str | None = None, wait: float = 15.0):
    subprocess.run(["taskkill", "/IM", "acad.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    if acad_exe:
        subprocess.Popen([acad_exe])
        time.sleep(wait)
    return connect_autocad()


def connect_or_restart_autocad(restart: bool = False, acad_exe: str | None = None):
    return restart_autocad(acad_exe=acad_exe) if restart else connect_autocad()


def find_or_open_document(acad, source_path: Path):
    source_path = source_path.resolve()
    try:
        count = com_retry(lambda: acad.Documents.Count)
        for index in range(count):
            doc = com_retry(lambda idx=index: acad.Documents.Item(idx))
            full_name = str(getattr(doc, "FullName", "") or "")
            if full_name.lower() == str(source_path).lower():
                com_retry(lambda: doc.ModelSpace.Count, attempts=40, delay=0.5)
                print(f"Found source drawing: {doc.Name}")
                return doc
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        com_retry(lambda: active.ModelSpace.Count, attempts=40, delay=0.5)
        print(f"Using readable active source drawing: {active.Name}")
        return active

    print(f"Opening source drawing: {source_path}")
    com_retry(lambda: acad.Documents.Open(str(source_path)), attempts=5, delay=2.0)
    opened = com_retry(lambda: acad.ActiveDocument)
    com_retry(lambda: opened.ModelSpace.Count, attempts=60, delay=0.5)
    return opened


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")


def object_name(entity) -> str:
    try:
        return str(entity.ObjectName)
    except Exception:
        return "UNKNOWN"


def collect_counts(space):
    counts = collections.Counter()
    total = com_retry(lambda: space.Count)
    for index in range(total):
        entity = com_retry(lambda idx=index: space.Item(idx))
        counts[object_name(entity)] += 1
    return total, counts


def annotation_total(counts: collections.Counter) -> int:
    return sum(count for name, count in counts.items() if any(token in name for token in ANNOTATION_TYPES))


def dimensions_total(counts: collections.Counter) -> int:
    return sum(count for name, count in counts.items() if "Dimension" in name or "Leader" in name)


def print_counts(label: str, total: int, counts: collections.Counter) -> None:
    print(f"{label} total entities: {total}")
    print(f"{label} dimensions/leaders: {dimensions_total(counts)}")
    print(f"{label} annotations: {annotation_total(counts)}")
    for name, count in counts.most_common():
        print(f"  {name}: {count}")


def copy_space(source_doc, source_space, target_space, label: str) -> int:
    total = com_retry(lambda: source_space.Count)
    if total == 0:
        print(f"{label}: no entities to copy.")
        return 0
    print(f"{label}: copying {total} entities.")
    batch = [com_retry(lambda idx=index: source_space.Item(idx)) for index in range(total)]
    objects = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, batch)
    com_retry(lambda: source_doc.CopyObjects(objects, target_space), attempts=10, delay=1.0)
    return total


def validate_space(source_space, target_space, label: str) -> bool:
    source_total, source_counts = collect_counts(source_space)
    target_total, target_counts = collect_counts(target_space)
    print_counts(f"Source {label}", source_total, source_counts)
    print_counts(f"Target {label}", target_total, target_counts)

    ok = source_total == target_total and source_counts == target_counts
    if not ok:
        print(f"WARNING: {label} entity distribution differs from source.")
    if dimensions_total(source_counts) != dimensions_total(target_counts):
        print(f"WARNING: {label} dimension/leader count differs from source.")
        ok = False
    return ok


def rebuild_dwg(source_doc, target_doc, include_paperspace: bool = True) -> bool:
    copy_space(source_doc, source_doc.ModelSpace, target_doc.ModelSpace, "ModelSpace")
    if include_paperspace:
        copy_space(source_doc, source_doc.PaperSpace, target_doc.PaperSpace, "PaperSpace")

    com_retry(lambda: target_doc.Activate())
    com_retry(lambda: target_doc.Regen(1))
    try:
        target_doc.Application.ZoomExtents()
    except Exception:
        pass

    valid = validate_space(source_doc.ModelSpace, target_doc.ModelSpace, "ModelSpace")
    if include_paperspace:
        valid = validate_space(source_doc.PaperSpace, target_doc.PaperSpace, "PaperSpace") and valid
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild a DWG through AutoCAD COM and validate entities.")
    parser.add_argument("--source", required=True, help="Source DWG file.")
    parser.add_argument("--output", default="outputs/redraw.dwg", help="Output DWG file.")
    parser.add_argument("--modelspace-only", action="store_true", help="Do not copy PaperSpace entities.")
    parser.add_argument("--restart-autocad", action="store_true", help="Restart AutoCAD before opening the source DWG.")
    parser.add_argument("--acad-exe", help="Optional acad.exe path used with --restart-autocad.")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    output_path = unique_output_path(Path(args.output).resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        raise FileNotFoundError(f"Source DWG not found: {source_path}")

    acad = connect_or_restart_autocad(restart=args.restart_autocad, acad_exe=args.acad_exe)
    source_doc = find_or_open_document(acad, source_path)
    target_doc = com_retry(lambda: acad.Documents.Add())
    print(f"Created target drawing: {target_doc.Name}")

    valid = rebuild_dwg(source_doc, target_doc, include_paperspace=not args.modelspace_only)
    com_retry(lambda: target_doc.SaveAs(str(output_path)))

    print(f"Saved DWG: {output_path}")
    print(f"Validation: {'PASS' if valid else 'CHECK WARNINGS'}")
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
