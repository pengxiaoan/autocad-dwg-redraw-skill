"""Rebuild a source DWG into a new DWG using AutoCAD COM automation.

Examples:
    python dwg_redraw.py --source input.dwg --output outputs/redraw_exact.dwg --exact
    python dwg_redraw.py --source input.dwg --output outputs/redraw_demo.dwg --record
    python dwg_redraw.py --source input.dwg --prepare-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT


def com_retry(action, attempts: int = 20, delay: float = 0.35):
    last_error = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    raise last_error


def connect_autocad():
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
    if restart:
        return restart_autocad(acad_exe=acad_exe)
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


def find_or_open_document(acad, source_path: Path):
    source_path = source_path.resolve()
    try:
        count = com_retry(lambda: acad.Documents.Count)
        for index in range(count):
            doc = com_retry(lambda idx=index: acad.Documents.Item(idx))
            full_name = str(getattr(doc, "FullName", "") or "")
            if full_name.lower() == str(source_path).lower():
                print(f"Found source drawing: {doc.Name}")
                return doc
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        full_name = str(getattr(active, "FullName", "") or "")
        if full_name.lower() == str(source_path).lower():
            print(f"Using active source drawing: {active.Name}")
            return active
        com_retry(lambda: active.ModelSpace.Count)
        print(f"Using readable active source drawing: {active.Name}")
        return active
    print(f"Opening source drawing: {source_path}")
    try:
        com_retry(lambda: acad.Documents.Open(str(source_path)))
        return com_retry(lambda: acad.ActiveDocument)
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        com_retry(lambda: active.ModelSpace.Count)
        print(f"Using readable active source drawing after open fallback: {active.Name}")
        return active


def start_screen_recorder(output_root: Path, fps: float, scale: float):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    record_dir = output_root / f"recording_{timestamp}"
    stop_file = record_dir / "stop_recording.flag"
    record_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--record-only",
        "--record-dir",
        str(record_dir),
        "--record-stop-file",
        str(stop_file),
        "--record-fps",
        str(fps),
        "--record-scale",
        str(scale),
    ]
    process = subprocess.Popen(command)
    time.sleep(1.0)
    return process, record_dir, stop_file


def stop_screen_recorder(process, stop_file: Path, timeout: float = 180.0) -> None:
    stop_file.write_text("stop", encoding="utf-8")
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=10)


def run_screen_recorder(record_dir: Path, stop_file: Path, fps: float, scale: float) -> int:
    import imageio.v2 as imageio
    import mss
    import numpy as np

    record_dir.mkdir(parents=True, exist_ok=True)
    video_path = record_dir / "screen_recording.mp4"
    interval = 1.0 / max(fps, 0.2)
    frame_count = 0
    print(f"Recording screen: {video_path}")

    with mss.MSS() as screen:
        monitor = screen.monitors[1]
        with imageio.get_writer(video_path, fps=max(fps, 0.2), codec="libx264", quality=7) as writer:
            while not stop_file.exists():
                started = time.time()
                shot = screen.grab(monitor)
                frame = np.asarray(shot)[:, :, :3][:, :, ::-1]
                if 0 < scale < 1:
                    height = max(1, int(frame.shape[0] * scale))
                    width = max(1, int(frame.shape[1] * scale))
                    rows = np.linspace(0, frame.shape[0] - 1, height).astype(int)
                    cols = np.linspace(0, frame.shape[1] - 1, width).astype(int)
                    frame = frame[rows][:, cols]
                writer.append_data(frame)
                frame_count += 1
                sleep_time = interval - (time.time() - started)
                if sleep_time > 0:
                    time.sleep(sleep_time)

    print(f"Recording complete: {video_path} ({frame_count} frames)")
    return 0 if frame_count else 1


def copy_entities_exact(source_doc, target_doc) -> int:
    model_space = source_doc.ModelSpace
    total = com_retry(lambda: model_space.Count)
    print(f"Source ModelSpace entities: {total}")
    print("Copying all entities in one operation for maximum fidelity.")
    batch = [com_retry(lambda idx=index: model_space.Item(idx)) for index in range(total)]
    objects = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, batch)
    com_retry(lambda: source_doc.CopyObjects(objects, target_doc.ModelSpace))
    com_retry(lambda: target_doc.Regen(1))
    try:
        target_doc.Application.ZoomExtents()
    except Exception:
        pass
    print(f"Target ModelSpace entities: {target_doc.ModelSpace.Count}")
    return total


def copy_entities_in_batches(source_doc, target_doc, batch_size: int, delay: float) -> int:
    model_space = source_doc.ModelSpace
    total = com_retry(lambda: model_space.Count)
    copied = 0
    print(f"Source ModelSpace entities: {total}")
    while copied < total:
        end = min(copied + batch_size, total)
        batch = [com_retry(lambda idx=index: model_space.Item(idx)) for index in range(copied, end)]
        objects = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, batch)
        com_retry(lambda: source_doc.CopyObjects(objects, target_doc.ModelSpace))
        copied = end
        com_retry(lambda: target_doc.Activate())
        com_retry(lambda: target_doc.Regen(1))
        try:
            target_doc.Application.ZoomExtents()
        except Exception:
            pass
        print(f"Redrawn entities: {copied}/{total}")
        if delay > 0:
            time.sleep(delay)
    return total


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild a DWG through AutoCAD COM.")
    parser.add_argument("--source", help="Source DWG file.")
    parser.add_argument("--output", default="outputs/redraw.dwg", help="Output DWG file.")
    parser.add_argument("--exact", action="store_true", help="Copy all ModelSpace entities in one operation.")
    parser.add_argument("--batch-size", type=int, default=22, help="Entities per visible redraw batch.")
    parser.add_argument("--step-delay", type=float, default=0.45, help="Delay between visible redraw batches.")
    parser.add_argument("--use-active-target", action="store_true", help="Use current active drawing as target.")
    parser.add_argument("--prepare-only", action="store_true", help="Open source and blank target, then stop.")
    parser.add_argument("--restart-autocad", action="store_true", help="Restart AutoCAD before opening the source DWG.")
    parser.add_argument("--acad-exe", help="Optional acad.exe path used with --restart-autocad.")
    parser.add_argument("--record", action="store_true", help="Record screen during redraw.")
    parser.add_argument("--record-fps", type=float, default=2.0, help="Recording frames per second.")
    parser.add_argument("--record-scale", type=float, default=0.5, help="Recording scale factor.")
    parser.add_argument("--record-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--record-dir", help=argparse.SUPPRESS)
    parser.add_argument("--record-stop-file", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.record_only:
        if not args.record_dir or not args.record_stop_file:
            raise ValueError("--record-only requires --record-dir and --record-stop-file")
        return run_screen_recorder(Path(args.record_dir), Path(args.record_stop_file), args.record_fps, args.record_scale)

    if not args.source:
        raise ValueError("--source is required unless --record-only is used")

    source_path = Path(args.source).resolve()
    output_path = unique_output_path(Path(args.output).resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.exists():
        raise FileNotFoundError(f"Source DWG not found: {source_path}")

    acad = connect_or_restart_autocad(restart=args.restart_autocad, acad_exe=args.acad_exe)
    source_doc = find_or_open_document(acad, source_path)

    if args.use_active_target and acad.ActiveDocument.FullName.lower() != str(source_path).lower():
        target_doc = acad.ActiveDocument
        print(f"Using active target drawing: {target_doc.Name}")
    else:
        target_doc = com_retry(lambda: acad.Documents.Add())
        print(f"Created target drawing: {target_doc.Name}")
    com_retry(lambda: target_doc.Activate())
    com_retry(lambda: target_doc.Regen(1))

    if args.prepare_only:
        print(f"Prepared blank redraw target. Source entities: {source_doc.ModelSpace.Count}")
        return 0

    recorder = None
    record_dir = None
    stop_file = None
    if args.record:
        recorder, record_dir, stop_file = start_screen_recorder(output_path.parent / "recordings", args.record_fps, args.record_scale)

    try:
        if args.exact:
            total = copy_entities_exact(source_doc, target_doc)
        else:
            total = copy_entities_in_batches(source_doc, target_doc, args.batch_size, args.step_delay)
        com_retry(lambda: target_doc.SaveAs(str(output_path)))
    finally:
        if recorder and stop_file:
            stop_screen_recorder(recorder, stop_file)

    print(f"Redraw complete. Source entities: {total}")
    print(f"Saved DWG: {output_path}")
    if record_dir:
        print(f"Saved recording: {record_dir / 'screen_recording.mp4'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
