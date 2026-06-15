"""Generate a standardized custom redraw prompt for a source AutoCAD DWG.

The script profiles a DWG through AutoCAD COM and writes a Markdown prompt that
can be used with the AutoCAD DWG Redraw skill.
"""

from __future__ import annotations

import argparse
import collections
import subprocess
import sys
import time
from pathlib import Path

import win32com.client


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
    acad.Visible = True
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
    return connect_autocad()


def find_or_open_document(acad, source_path: Path):
    source_path = source_path.resolve()
    try:
        count = com_retry(lambda: acad.Documents.Count)
        for index in range(count):
            doc = com_retry(lambda idx=index: acad.Documents.Item(idx))
            full_name = str(getattr(doc, "FullName", "") or "")
            if full_name.lower() == str(source_path).lower():
                return doc
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        full_name = str(getattr(active, "FullName", "") or "")
        if full_name.lower() == str(source_path).lower():
            return active
        com_retry(lambda: active.ModelSpace.Count)
        return active
    try:
        com_retry(lambda: acad.Documents.Open(str(source_path)))
        return com_retry(lambda: acad.ActiveDocument)
    except Exception:
        active = com_retry(lambda: acad.ActiveDocument)
        com_retry(lambda: active.ModelSpace.Count)
        return active


def safe_get(obj, attr: str, default=""):
    try:
        value = getattr(obj, attr)
        return value if value is not None else default
    except Exception:
        return default


def collect_layers(doc):
    rows = []
    try:
        count = doc.Layers.Count
        for index in range(count):
            layer = doc.Layers.Item(index)
            rows.append(
                {
                    "name": safe_get(layer, "Name"),
                    "color": safe_get(layer, "Color"),
                    "linetype": safe_get(layer, "Linetype"),
                    "lineweight": safe_get(layer, "Lineweight"),
                }
            )
    except Exception as exc:
        rows.append({"name": f"ERROR: {exc}", "color": "", "linetype": "", "lineweight": ""})
    return rows


def collect_named_collection(collection, name_attr="Name"):
    names = []
    try:
        count = collection.Count
        for index in range(count):
            item = collection.Item(index)
            names.append(str(safe_get(item, name_attr)))
    except Exception as exc:
        names.append(f"ERROR: {exc}")
    return names


def collect_entity_counts(space):
    counts = collections.Counter()
    layers = collections.Counter()
    total = com_retry(lambda: space.Count)
    for index in range(total):
        entity = com_retry(lambda idx=index: space.Item(idx))
        counts[str(safe_get(entity, "ObjectName", "UNKNOWN"))] += 1
        layers[str(safe_get(entity, "Layer", "UNKNOWN"))] += 1
    return total, counts, layers


def classify_drawing(block_names, entity_counts):
    upper_blocks = [name.upper() for name in block_names]
    has_bom = any("BOM" in name or "BILL" in name or "明细" in name for name in upper_blocks)
    has_title = any("A0" in name or "A1" in name or "A2" in name or "A3" in name or "TITLE" in name for name in upper_blocks)
    has_many_blocks = sum(entity_counts.values()) and entity_counts.get("AcDbBlockReference", 0) > 20
    if has_bom:
        return "装配图", "检测到 BOM/明细栏相关块，通常表示装配图。"
    if has_title and has_many_blocks:
        return "工程图/布局图", "检测到图框块和较多块引用。"
    return "未知或零件图", "未检测到明确 BOM 线索，需要人工复核标题栏和视图内容。"


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def render_prompt(source_path, doc, layers, text_styles, dim_styles, blocks, model_total, paper_total, entity_counts, layer_counts):
    classification, reason = classify_drawing(blocks, entity_counts)
    basename = source_path.stem
    file_size = source_path.stat().st_size

    entity_rows = [{"ObjectName": name, "Count": count} for name, count in entity_counts.most_common()]
    layer_count_rows = [{"Layer": name, "EntityCount": count} for name, count in layer_counts.most_common()]
    block_rows = [{"BlockName": name} for name in blocks]
    style_rows = [{"TextStyle": name} for name in text_styles]
    dim_rows = [{"DimStyle": name} for name in dim_styles]

    return f"""# {basename} 重绘提示词定制版

## 1. 图纸指纹

- 源 DWG：`{source_path.name}`
- 文件大小：{file_size} bytes
- AutoCAD 文档名：`{safe_get(doc, "Name")}`
- ModelSpace 实体数：{model_total}
- PaperSpace 实体数：{paper_total}
- 初步分类：{classification}
- 分类依据：{reason}

## 2. 标准重绘策略

- 最终交付必须使用精确模式：一次性复制全部 ModelSpace 实体，避免分批复制导致关联标注或依赖块重复。
- 视频演示可以使用逐批模式，但逐批结果只作为录屏素材，不作为最终验收 DWG。
- 不覆盖源 DWG，所有输出写入 `outputs/` 或用户指定目录。
- 如果需要生成 AutoLISP/Python 源码，而不是复制实体，必须先导出 DXF 或 DATAEXTRACTION 表，再按实体坐标逐条生成代码。

## 3. 推荐执行命令

最终精确重绘：

```powershell
python scripts\\dwg_redraw.py --source "{source_path.name}" --output "outputs\\{basename}_最终精确重绘.dwg" --exact
```

录屏逐批重绘：

```powershell
python scripts\\dwg_redraw.py --source "{source_path.name}" --output "outputs\\{basename}_逐批重绘_recorded.dwg" --batch-size 22 --step-delay 0.45 --record
```

先打开空白页面，等待用户输入开始：

```powershell
python scripts\\dwg_redraw.py --source "{source_path.name}" --prepare-only
python scripts\\dwg_redraw.py --source "{source_path.name}" --output "outputs\\{basename}_等待后开始_recorded.dwg" --use-active-target --batch-size 22 --step-delay 0.45 --record
```

## 4. 图层清单

{markdown_table(["name", "color", "linetype", "lineweight"], layers)}

## 5. 实体类型分布

{markdown_table(["ObjectName", "Count"], entity_rows)}

## 6. 实体所在图层分布

{markdown_table(["Layer", "EntityCount"], layer_count_rows)}

## 7. 块清单

{markdown_table(["BlockName"], block_rows)}

## 8. 文字样式

{markdown_table(["TextStyle"], style_rows)}

## 9. 标注样式

{markdown_table(["DimStyle"], dim_rows)}

## 10. 如果需要代码级重绘，必须补充的数据

在 AutoCAD 中执行：

```text
DXFOUT
DATAEXTRACTION
-LAYER ? *
-STYLE ? *
-DIMSTYLE ? *
LIST
```

并补充：

- 所有 LINE/LWPOLYLINE/CIRCLE/ARC/TEXT/MTEXT/HATCH/DIMENSION 的精确坐标。
- 所有块定义和块插入属性。
- 标题栏、明细栏、粗糙度、基准、形位公差的块名、插入点、旋转角、属性值。
- 旧版 DWG 的字体编码、SHX 字体、大字体设置。

## 11. 验证标准

- 源图 ModelSpace 实体数 = 最终精确重绘图 ModelSpace 实体数 = {model_total}
- PaperSpace 实体数符合预期 = {paper_total}
- `ZOOM EXTENTS` 后图形完整可见。
- 标题栏、明细栏、块插入、文字、标注、中心线、虚线和剖面线视觉一致。
- 如果逐批录屏版实体数不同，使用精确版作为最终交付。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a standardized DWG redraw custom prompt.")
    parser.add_argument("--source", required=True, help="Source DWG file.")
    parser.add_argument("--output", help="Output Markdown prompt path.")
    parser.add_argument("--restart-autocad", action="store_true", help="Restart AutoCAD before opening the source DWG.")
    parser.add_argument("--acad-exe", help="Optional acad.exe path used with --restart-autocad.")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source DWG not found: {source_path}")

    output_path = Path(args.output).resolve() if args.output else source_path.with_name(f"{source_path.stem}-redraw-prompt.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    acad = connect_or_restart_autocad(restart=args.restart_autocad, acad_exe=args.acad_exe)
    doc = find_or_open_document(acad, source_path)
    model_total, entity_counts, layer_counts = collect_entity_counts(doc.ModelSpace)
    paper_total = com_retry(lambda: doc.PaperSpace.Count)
    layers = collect_layers(doc)
    text_styles = collect_named_collection(doc.TextStyles)
    dim_styles = collect_named_collection(doc.DimStyles)
    blocks = collect_named_collection(doc.Blocks)

    prompt = render_prompt(
        source_path,
        doc,
        layers,
        text_styles,
        dim_styles,
        blocks,
        model_total,
        paper_total,
        entity_counts,
        layer_counts,
    )
    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote custom redraw prompt: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Prompt generation failed: {exc}", file=sys.stderr)
        raise
