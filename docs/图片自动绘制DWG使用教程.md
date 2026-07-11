# 图片自动绘制 DWG 使用教程

本教程介绍如何使用 `autocad-image-redraw`，把 JPG、JPEG、PNG、扫描件、截图、手绘草图或拍摄的工程图，整理为可编辑的 AutoCAD DWG/DXF，并完成输入检查、规格校验、CAD 检查和图片对比。

## 1. GitHub 地址

- GitHub 仓库：<https://github.com/pengxiaoan/autocad-dwg-redraw-skill>
- 图片转 DWG Skill：<https://github.com/pengxiaoan/autocad-dwg-redraw-skill/tree/main/skills/autocad-image-redraw>
- Skill 主说明：<https://github.com/pengxiaoan/autocad-dwg-redraw-skill/blob/main/skills/autocad-image-redraw/SKILL.md>
- 校验规范：<https://github.com/pengxiaoan/autocad-dwg-redraw-skill/blob/main/skills/autocad-image-redraw/references/image-redraw-validation.md>

克隆仓库：

```powershell
git clone https://github.com/pengxiaoan/autocad-dwg-redraw-skill.git
cd autocad-dwg-redraw-skill
```

## 2. 功能范围

这套工作流可以处理：

- 手绘建筑平面图、房间布局图；
- 机械零件照片、草图和尺寸图；
- AutoCAD 截图或导出的 PNG/JPG；
- 扫描的旧图纸；
- 带有尺寸、文字、门窗、孔位、圆弧和表格的图片；
- 只需要轮廓、不需要文字与尺寸的纯几何重绘。

最终可交付：

- 可编辑 DWG；
- 用于审计和预览的 DXF；
- 图片重绘规格 JSON；
- 输入质量、规格和 DWG 检查报告；
- CAD 预览 PNG/PDF；
- 原图与 CAD 的并排图、叠加图、差异图及误差指标。

图片重绘不等于自动恢复原始设计数据。只有图片中存在可靠单位、尺寸和标定依据时，才能声明工程尺寸准确；单纯视觉相似不能证明实际尺寸正确。

## 3. 环境准备

### 3.1 推荐环境

- Windows 10 或 Windows 11；
- 已安装 AutoCAD；
- Python 3.10 或更高版本；
- 已安装 Codex；
- AutoCAD COM 功能可以正常启动。

安装 Python 依赖：

```powershell
python -m pip install pywin32 pillow numpy opencv-python ezdxf pymupdf
```

依赖用途：

- `pywin32`：控制 AutoCAD，生成和检查 DWG；
- `Pillow`、`OpenCV`、`NumPy`：读取、检查和比较图片；
- `ezdxf`：检查和读取 DXF；
- `PyMuPDF`：生成固定页面的 PNG/PDF 预览。

### 3.2 安装 Skill

在 PowerShell 中运行：

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo pengxiaoan/autocad-dwg-redraw-skill `
  --path skills/autocad-image-redraw
```

安装后重新启动 Codex。Skill 默认位置通常是：

```text
C:\Users\你的用户名\.codex\skills\autocad-image-redraw
```

## 4. 选择重绘模式

| 模式 | 适用情况 | 尺寸要求 |
|---|---|---|
| `strict-dimensioned` | 正式工程图、加工图、要求尺寸准确 | 必须有单位和可靠尺寸/标定锚点 |
| `general` | 普通平面图、草图、截图 | 默认模式，允许记录不确定项 |
| `hybrid` | 部分区域有尺寸、部分区域只能按比例恢复 | 有尺寸区域必须校验，其余标记为推断 |
| `visual-trace` | 只要求看起来接近原图 | 可以使用 `unitless`，不能声明真实尺寸准确 |
| `geometry-only` | 只要墙线、轮廓、孔、圆弧等几何 | 自动排除文字、尺寸和引线 |

不确定时优先使用 `general`。如果图片没有任何单位或已知长度，不要直接假设单位为毫米，应选择 `visual-trace` 或 `unitless`。

## 5. 最简单的 Codex 使用方法

把图片拖入 Codex，然后输入：

```text
使用 $autocad-image-redraw 处理这张图片。
先检查图片质量和可用尺寸，选择合适的重绘模式；
生成证据可追踪的重绘规格 JSON；
使用 AutoCAD 绘制可编辑 DWG，并导出 DXF 和预览图；
检查 DWG 的单位、图层和实体；
把 CAD 结果与原图进行叠加和差异比较；
发现问题后继续优化，最后报告已知尺寸、推断内容和未解决问题。
```

只绘制几何、不需要尺寸和文字：

```text
使用 $autocad-image-redraw，以 geometry-only 模式重绘这张图片。
保留轮廓、墙体、门窗、孔、圆弧和必要中心线，删除尺寸、文字、引线和表格内容。
完成后检查 DWG，并和原图进行几何对比。
```

要求尺寸优先：

```text
使用 $autocad-image-redraw，以 strict-dimensioned 模式处理图片。
图片中的明确尺寸和我提供的数据优先，禁止用像素比例覆盖已知尺寸。
如果单位、尺寸端点或标定依据不足，请停止尺寸精确声明并列出阻塞项。
```

## 6. 标准项目目录

建议为每张图建立独立目录：

```text
image-redraw-project/
├─ source/
│  └─ input.jpg
├─ specs/
│  ├─ redraw-spec.json
│  └─ comparison-anchors.json
├─ outputs/
│  ├─ redraw.dwg
│  └─ redraw.dxf
└─ reports/
   ├─ input-preflight.json
   ├─ spec-validation.json
   ├─ dwg-inspection.json
   ├─ cad-preview.png
   ├─ cad-preview.pdf
   └─ comparison/
```

## 7. 完整命令行流程

下面假设 Skill 安装在：

```powershell
$Skill = "$env:USERPROFILE\.codex\skills\autocad-image-redraw"
```

### 第一步：检查输入图片

普通模式：

```powershell
python "$Skill\scripts\preflight_image_redraw.py" `
  --image "source\input.jpg" `
  --mode general `
  --output "reports\input-preflight.json"
```

已确认图纸单位为毫米时，可以增加：

```powershell
--units mm
```

预检会记录：

- 图片文件哈希；
- 图片尺寸和方向；
- 模糊度和对比度指标；
- 标定锚点数量；
- 警告、阻塞项和建议操作。

### 第二步：生成重绘规格 JSON

通常由 Codex 根据图片生成 `specs\redraw-spec.json`。规格至少包含：

```json
{
  "schema_version": "2.0",
  "metadata": {
    "title": "图片重绘",
    "units": "mm",
    "profile": "hybrid",
    "source_image": "source/input.jpg"
  },
  "views": [
    {
      "id": "main-plan",
      "source_roi": [0, 0, 960, 1081],
      "cad_origin": [0, 0],
      "scale_group": "main-plan"
    }
  ],
  "calibration": [],
  "constraints": [],
  "layers": [],
  "entities": [],
  "validation": {}
}
```

重要数据需要标注来源等级：

- `known`：用户提供或图片中清楚可读；
- `scaled`：使用可靠锚点标定后测量；
- `inferred`：根据对称、连续关系或经验推断；
- `unreadable`：图片中可见但无法可靠识别。

### 第三步：绘图前校验规格

```powershell
python "$Skill\scripts\validate_image_redraw_spec.py" `
  --spec "specs\redraw-spec.json" `
  --profile general `
  --report "reports\spec-validation.json"
```

此步骤会检查：

- JSON 是否完整；
- 单位、模式、实体类型是否受支持；
- 坐标和半径是否合法；
- 实体 ID 是否重复；
- 视图引用和标定数据是否有效；
- 尺寸链和数值约束是否满足；
- 严格尺寸模式是否具备足够依据。

### 第四步：先执行 dry-run

```powershell
python "$Skill\scripts\draw_image_spec.py" `
  --spec "specs\redraw-spec.json" `
  --dry-run
```

确认实体数量、单位和过滤规则正确后，再连接 AutoCAD。

### 第五步：生成 DWG

```powershell
python "$Skill\scripts\draw_image_spec.py" `
  --spec "specs\redraw-spec.json" `
  --output "outputs\redraw.dwg"
```

如果输出文件已经存在：

```powershell
--overwrite
```

纯几何模式：

```powershell
python "$Skill\scripts\draw_image_spec.py" `
  --spec "specs\redraw-spec.json" `
  --output "outputs\redraw-geometry.dwg" `
  --geometry-only
```

中文显示异常时：

```powershell
python "$Skill\scripts\draw_image_spec.py" `
  --spec "specs\redraw-spec.json" `
  --output "outputs\redraw.dwg" `
  --text-style CN_TEXT `
  --text-font "C:\Windows\Fonts\simhei.ttf"
```

AutoCAD 打开多个窗口、COM 连接到开始页时：

```powershell
--attach-document "C:\路径\任意可正常打开的.dwg"
```

### 第六步：检查 DWG

```powershell
python "$Skill\scripts\inspect_dwg_output.py" `
  --dwg "outputs\redraw.dwg" `
  --expected-units mm `
  --required-layers "OBJECT,DIM,TEXT" `
  --report "reports\dwg-inspection.json"
```

纯几何文件应增加：

```powershell
--geometry-only
```

检查内容包括：

- DWG 是否可以打开；
- ModelSpace 是否为空；
- 插入单位是否符合要求；
- 必要图层是否存在；
- 实体类型和数量；
- 纯几何文件是否错误包含文字或尺寸。

### 第七步：导出 DXF 并生成预览

在 AutoCAD 中把 DWG 另存为 DXF，然后运行：

```powershell
python "$Skill\scripts\render_dxf_preview.py" `
  --dxf "outputs\redraw.dxf" `
  --png "reports\cad-preview.png" `
  --pdf "reports\cad-preview.pdf" `
  --page A3 `
  --orientation landscape `
  --dpi 300 `
  --report "reports\dxf-preview-report.json"
```

脚本会先执行 DXF 审计。存在严重 DXF 错误时，不应继续把预览当作有效校验依据。

### 第八步：准备图片对比锚点

对于一个平面视图，至少选择四个分布均匀的对应点：

```json
{
  "source_points": [[245, 91], [562, 94], [567, 638], [260, 512]],
  "cad_points": [[100, 100], [900, 100], [900, 1200], [100, 1200]]
}
```

- `source_points`：原图像素坐标；
- `cad_points`：CAD 预览 PNG 中的像素坐标；
- 两组点必须一一对应；
- 点应尽量靠近视图四周，不要集中在一个小区域。

一张照片包含多个比例或透视不同的区域时，分别定义视图：

```json
{
  "views": [
    {
      "id": "upper-plan",
      "source_roi": [100, 50, 600, 650],
      "source_points": [[120, 80], [580, 80], [580, 620], [120, 620]],
      "cad_points": [[100, 100], [900, 100], [900, 1100], [100, 1100]]
    },
    {
      "id": "lower-detail",
      "source_roi": [100, 650, 850, 1050],
      "source_points": [[120, 680], [820, 680], [820, 1020], [120, 1020]],
      "cad_points": [[100, 1200], [1200, 1200], [1200, 1800], [100, 1800]]
    }
  ]
}
```

### 第九步：比较原图与 CAD

```powershell
python "$Skill\scripts\compare_redraw.py" `
  --source "source\input.jpg" `
  --cad-preview "reports\cad-preview.png" `
  --anchors "specs\comparison-anchors.json" `
  --output-dir "reports\comparison"
```

输出包括：

- `side-by-side.png`：原图和 CAD 并排；
- `registered-cad.png`：配准到原图位置的 CAD；
- `overlay.png`：半透明叠加图；
- `edge-difference.png`：边缘差异图；
- `metrics.json`：边缘距离和覆盖率指标。

重点查看：

- 是否漏画墙线、孔、门窗或圆弧；
- 轮廓是否明显偏移；
- 门洞方向和圆弧方向是否错误；
- 多个视图的位置关系是否正确；
- CAD 是否出现原图没有的多余几何。

## 8. 如何理解校验状态

| 状态 | 含义 |
|---|---|
| `pass` | 当前模式要求的必要检查全部通过 |
| `pass_with_warnings` | 可以使用，但存在已记录的非关键不确定项 |
| `needs_review` | 需要人工选择，例如两个尺寸互相冲突 |
| `blocked` | 缺少所选模式必须具备的证据 |
| `fail` | 规格错误、DWG 损坏或强制约束失败 |

不要为了得到 `pass` 而偷偷降低模式。例如从 `strict-dimensioned` 改为 `visual-trace` 时，必须在最终报告中说明。

## 9. 推荐优化顺序

第一次对比发现问题后，按下面顺序优化：

1. 单位、总尺寸和主要定位轴线；
2. 外轮廓和墙体拓扑；
3. 门窗、孔、槽和圆弧；
4. 内部尺寸链和重复结构；
5. 图层、线型、中心线和隐藏线；
6. 尺寸、文字、表格和标题栏；
7. 视觉布局、文字避让和打印效果。

每次只修复一组高影响问题，然后重新生成 DWG、DXF 和对比报告，避免修改后没有重新验证。

## 10. 常见问题

### 图片很模糊，还能绘制吗？

可以先恢复确定的轮廓，但无法识别的文字和尺寸必须标记为 `unreadable`。如果关键尺寸无法读取，应请求更高清图片或用户提供尺寸。

### 图片没有任何尺寸怎么办？

使用 `visual-trace` 和 `unitless`，只声明视觉重绘。也可以让用户提供一个已知长度作为标定锚点，再切换到 `hybrid`。

### 为什么不能只按图片像素直接转换？

照片可能存在透视、纸张弯曲、镜头畸变和不同视图比例。像素一致只能说明视觉接近，不能说明 CAD 中的毫米尺寸正确。

### AutoCAD COM 报错或连接到开始页怎么办？

先打开一个正常 DWG，再使用 `--attach-document` 指向它。关闭不必要的 AutoCAD 实例，并避免在脚本绘制期间频繁切换或关闭文档。

### 中文显示成问号怎么办？

明确指定 `CN_TEXT` 和中文字体，例如 `C:\Windows\Fonts\simhei.ttf`，然后重新生成 DWG。

### 只想要一个粗略 DXF，不安装 AutoCAD可以吗？

可以使用开源视觉矢量化路径：

```powershell
python "$Skill\scripts\image_to_dxf_open_source.py" `
  --image "source\input.jpg" `
  --output "outputs\rough-vector.dxf" `
  --preview "reports\rough-vector.png" `
  --circles
```

该结果主要是像素线条的可编辑基线，不会自动恢复真正的工程尺寸、尺寸标注语义或设计意图。

## 11. 最终交付检查表

交付前确认：

- 原始图片和哈希已保存；
- 已明确选择重绘模式；
- 单位和标定依据有记录；
- 已知、标定、推断和不可读内容已区分；
- 规格校验通过或警告已解释；
- DWG 可以打开并且不是空文件；
- DWG 单位、图层和实体符合要求；
- DXF 审计通过；
- 已生成固定页面预览；
- 已完成原图/CAD 并排、叠加和差异比较；
- 最终状态和剩余不确定项已写入报告。

## 12. 推荐的一句话任务模板

```text
使用 $autocad-image-redraw，把我提供的图片重绘为可编辑 DWG。
先进行输入质量和尺寸证据检查，再生成并验证重绘规格；
使用 AutoCAD 绘制，导出 DWG、DXF 和预览；
检查单位、图层、实体及尺寸约束；
将 CAD 与原图进行配准、叠加和边缘差异比较；
根据结果继续优化，直到当前模式通过，并明确列出所有推断和不可读内容。
```
