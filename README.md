# Dye2SMILES

本地染料/分子结构转 RDKit SMILES 工具。支持把 ChemDraw / Mol / SDF 文件转换为 RDKit canonical SMILES；macOS 打包版已内置 OSRA，可识别截图、PNG、JPG、PDF 等图像输入。Windows 版可用同一套界面和 RDKit 核心；截图识别需要提供 Windows OSRA runtime 或设置 `OSRA_PATH`。

项目早期名称是 LCSMILES；内部 Python 包名仍保留为 `lcsmiles`，方便保持兼容。

## 功能

- 支持 `.cdxml`、`.cdx`、`.mol`、`.sdf`、`.smi`、`.smiles`
- macOS 打包版内置 OSRA，支持 `.png`、`.jpg`、`.jpeg`、`.tif`、`.tiff`、`.pdf`
- Windows 打包配置已提供；如放入 Windows OSRA runtime，可一并打包截图识别能力
- 输出 RDKit canonical SMILES，默认保留立体化学
- 本地 Tkinter 图形界面，不需要服务器
- 命令行批量转换
- CSV 导出
- PyInstaller 打包脚本，适合生成 Windows / macOS 本地软件
- 截图/PDF 图片输入会统一标记为“需检查”，因为 OCSR 不能可靠保证手性楔线和双键顺反

## 目录

```text
Dye2SMILES/
  src/lcsmiles/
    core.py          # 文件识别、RDKit 转换、SMILES 标准化
    ocsr.py          # OSRA 图像识别适配
    cli.py           # 命令行入口
    gui.py           # 本地图形界面
  scripts/
    run_app.command  # macOS 双击运行
    run_app.bat      # Windows 双击运行
    build_macos.sh   # macOS 打包
    build_windows.bat# Windows 打包
    create_windows_env.bat # Windows conda 环境创建
  tests/
  sample_data/
```

## 安装

建议使用 conda，因为 RDKit 在 conda-forge 上最稳定。

```bash
cd "Dye2SMILES"
conda env create -f environment.yml
conda activate lcsmiles
```

如果不想用 `environment.yml`，也可以手动安装：

```bash
conda create -n lcsmiles python=3.11 rdkit -c conda-forge
conda activate lcsmiles
python -m pip install -e ".[dev]"
```

如果你不用 conda，也可以尝试：

```bash
cd "Dye2SMILES"
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
cd "Dye2SMILES"
conda env create -f environment-windows.yml
conda activate lcsmiles-win
```

## 启动本地软件

```bash
python -m lcsmiles.gui
```

或双击：

- macOS: `scripts/run_app.command`
- Windows: `scripts/run_app.bat`

## 命令行转换

```bash
python -m lcsmiles.cli samples/example.cdxml -o output.csv
```

批量输入：

```bash
python -m lcsmiles.cli file1.cdxml file2.sdf image.png -o output.csv
```

## 截图 / 图片识别

macOS 打包版已内置 OSRA，不需要用户自己安装 OSRA 或 RDKit。

如果使用源码运行，项目会优先使用 `packaging/osra-runtime` 里的内置 OSRA；如果这个目录不存在，也可以安装系统 OSRA，或设置环境变量：

```powershell
$env:OSRA_PATH="C:\path\to\osra.exe"
```

注意：截图识别属于 OCSR，准确率受图片质量、缩写、手性标注、噪声影响很大。软件会用 RDKit 再校验输出，但最终结果仍建议人工确认。

Dye2SMILES 对结构文件和 SMILES 输入默认保留 RDKit 可解析的立体化学，例如 `@` / `@@` 手性中心和 `/` / `\` 双键顺反。截图输入不同：如果 OSRA 没有从图片里读出楔线或 E/Z 信息，RDKit 不能凭空恢复。因此图片输入即使能得到合法 SMILES，也会显示“需检查”。


质量验证脚本：

```bash
python scripts/verify_quality_suite.py
```

该脚本会检查核心层手性/顺反保留、已知染料截图回归样本，以及 OSRA 对生成图片的手性识别边界。

## 打包

macOS:

```bash
scripts/build_macos.sh
```

Windows:

```bat
scripts\build_windows.bat
```

打包结果在 `dist/` 目录。

Windows 详细说明见 [WINDOWS_BUILD.md](WINDOWS_BUILD.md)。注意：当前 OSRA 2.2.4 Windows 官方二进制是购买下载，conda-forge 没有 `win-64` OSRA 包。没有 OSRA 时，Windows app 仍可转换 ChemDraw / MOL / SDF / SMILES；截图/PDF 识别需要打包 Windows OSRA runtime 或设置 `OSRA_PATH`。

## 当前边界

- RDKit 对 ChemDraw CDXML/CDX 的支持不是 ChemDraw 全功能复刻，复杂对象可能解析失败。
- 截图识别使用 OSRA，结果必须人工确认。
- 如果 ChemDraw 文件里有多个结构，会输出多行 SMILES。
