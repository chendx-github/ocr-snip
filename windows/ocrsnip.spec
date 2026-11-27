# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows onedir）。

为什么要 onedir 而不是 onefile：onedir 启动快（不用每次解压到临时目录），
而这是个"按热键就要秒开"的工具，onefile 的 300MB 自解压会让首启慢好几秒。

用法（在仓库根目录）：
    pyinstaller windows/ocrsnip.spec --noconfirm
产物：
    windows/dist/ocrsnip/ocrsnip.exe
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH 由 PyInstaller 注入)
ICON = str(ROOT / "windows" / "ocrsnip.ico")
VERSION_FILE = str(ROOT / "windows" / "version_info.txt")

# rapidocr 的模型（.onnx）、配置（.yaml）、字典都在包内，必须一起带走；
# 少了它们程序能起来但一识别就报"找不到模型"。
datas = collect_data_files("rapidocr", include_py_files=False)
datas += collect_data_files("onnxruntime", include_py_files=False)

hiddenimports = [
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "rapidocr",
    *collect_submodules("rapidocr"),
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
]

# 砍掉用不到的 Qt 组件，安装包能小一半以上
excludes = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "tkinter",
    "matplotlib",
    "pandas",
    "scipy",
    "IPython",
    "pytest",
    "setuptools",
    "pip",
]

a = Analysis(
    [str(ROOT / "windows" / "entry.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# ---- 体积裁剪：删掉确定用不到的大件 ----
# 1) opencv 的 ffmpeg 后端插件（Windows 上的 opencv_videoio_ffmpeg*.dll 是懒加载插件，
#    删掉不影响图片处理；Linux 的 cv2 直接链 libav*，不能删）
# 2) Qt 的翻译文件与 QtQuick/Qml 运行库（托盘小工具不需要）
_DENY = (
    "opencv_videoio_ffmpeg",
    "OpenCV videoio ffmpeg",
    "PySide6/translations",
    "PySide6\\translations",
    "qtwebengine",
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Charts",
    "Qt6DataVisualization",
)


def _keep(entry) -> bool:
    name = str(entry[0]).lower()
    return not any(token.lower() in name for token in _DENY)


a.binaries = [entry for entry in a.binaries if _keep(entry)]
a.datas = [entry for entry in a.datas if _keep(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ocrsnip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 托盘程序，不要黑框
    disable_windowed_traceback=False,
    icon=ICON,
    version=VERSION_FILE if os.path.exists(VERSION_FILE) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ocrsnip",
)
