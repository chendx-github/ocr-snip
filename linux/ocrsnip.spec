# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Linux onedir）。

onedir 而不是 onefile：这是个"按热键就要秒开"的工具，onefile 每次启动都要把
上百 MB 解压到临时目录，首启会慢好几秒。

用法（仓库根目录）：
    pyinstaller linux/ocrsnip.spec --noconfirm
产物：
    linux/dist/ocrsnip/ocrsnip
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH 由 PyInstaller 注入)
ICON = str(ROOT / "linux" / "ocrsnip.png")

# rapidocr 的模型（.onnx）、配置（.yaml）、字典都在包内，必须一起带走
datas = collect_data_files("rapidocr", include_py_files=False)
datas += collect_data_files("onnxruntime", include_py_files=False)
datas += [(ICON, "icon")]

hiddenimports = [
    "onnxruntime",
    "onnxruntime.capi._pybind_state",
    "rapidocr",
    *collect_submodules("rapidocr"),
    "PySide6.QtNetwork",
    "PySide6.QtSvg",
    "Xlib",
    "Xlib.display",
    "Xlib.protocol",
]

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
    "PySide6.QtDBus",
    "PySide6.QtXml",
    "PySide6.QtConcurrent",
    "PySide6.QtUiTools",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.QtStateMachine",
    "PySide6.QtTextToSpeech",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtHttpServer",
    "PySide6.QtGraphs",
    "PySide6.QtLocation",
    "PySide6.QtNfc",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.QtWebView",
    "gi",
    "gobject",
    "cairo",
    "tkinter",
    "matplotlib",
    "pandas",
    "scipy",
    "IPython",
    "pytest",
]

a = Analysis(
    [str(ROOT / "linux" / "entry.py")],
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ocrsnip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
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
