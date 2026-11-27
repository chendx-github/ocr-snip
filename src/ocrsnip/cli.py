"""命令行入口：ocrsnip {daemon,capture,status,stop,doctor,config}。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path

from . import __version__
from .config import (
    DEFAULT_CONFIG_TOML,
    Config,
    config_path,
    ipc_name,
    is_windows,
    last_png_path,
    log_path,
    socket_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ocrsnip",
        description="按下热键 → 框选 → 把选中的文字放进剪贴板",
    )
    parser.add_argument("--config", type=Path, default=None, help="配置文件路径")
    parser.add_argument(
        "--ui",
        choices=("auto", "gtk", "qt"),
        default="auto",
        help="界面后端：auto=Windows 用 qt、Linux 用 gtk",
    )
    parser.add_argument("--selftest", action="store_true", help="等价于 `selftest` 子命令")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    p_daemon = sub.add_parser("daemon", help="前台运行守护进程（一般交给 systemd）")
    _add_ui_option(p_daemon)
    p_capture = sub.add_parser("capture", help="立即触发一次截屏识别（走 daemon）")
    p_capture.add_argument("--stdout", action="store_true", help="同时把结果打印到终端")
    _add_ui_option(p_capture)
    sub.add_parser("status", help="查看 daemon 状态")
    sub.add_parser("stop", help="停止 daemon")
    sub.add_parser("doctor", help="自检：热键、抓屏、OCR 预热耗时、依赖")
    p_config = sub.add_parser("config", help="显示配置文件路径/生成模板")
    p_config.add_argument("--init", action="store_true", help="写入默认配置模板")
    p_config.add_argument("--print", action="store_true", help="打印当前配置")
    p_selftest = sub.add_parser("selftest", help="自检：OCR 是否能识别（Windows 装机后先跑这个）")
    _add_ui_option(p_selftest)
    sub.add_parser("version", help="版本号")

    args = parser.parse_args(argv)
    command = args.command or ("selftest" if args.selftest else "daemon")

    if command == "version":
        print(__version__)
        return 0

    cfg = Config.load(args.config)
    if command == "config":
        return _cmd_config(cfg, args)
    if command == "doctor":
        return _cmd_doctor(cfg)
    if command == "status":
        return _cmd_status(cfg)
    if command == "stop":
        return _cmd_stop()
    if command == "capture":
        return _cmd_capture(cfg, args.stdout, args.ui)
    if command == "daemon":
        return _cmd_daemon(cfg, args.ui)
    if command == "selftest":
        return _cmd_selftest(cfg, args.ui)
    parser.error(f"未知命令 {command}")
    return 2


# ---------------------------------------------------------------- daemon
def _add_ui_option(parser: argparse.ArgumentParser) -> None:
    """子命令也接受 --ui；用 SUPPRESS 保证不覆盖全局 --ui 的取值。"""
    parser.add_argument(
        "--ui",
        choices=("auto", "gtk", "qt"),
        default=argparse.SUPPRESS,
        help="界面后端（同全局 --ui）",
    )


def _pick_ui(requested: str = "auto") -> str:
    if requested in ("gtk", "qt"):
        return requested
    # 打包版只有 Qt（GTK/PyGObject 没法随包带走），由 entry 设 OCRSNIP_UI=qt
    env = os.environ.get("OCRSNIP_UI", "").strip().lower()
    if env in ("gtk", "qt"):
        return env
    return "qt" if is_windows() else "gtk"


def _cmd_daemon(cfg: Config, ui: str = "auto") -> int:
    _setup_logging(cfg)
    for warning in cfg.warnings:
        _warn(f"配置警告：{warning}")

    if _pick_ui(ui) == "qt":
        from .qt_app import QtBackend, create_app

        create_app()
        return QtBackend(cfg).run()

    from . import display_env

    display_env.ensure_display(timeout=5.0)
    from .daemon import Daemon

    return Daemon(cfg).run()


# ---------------------------------------------------------------- capture
def _cmd_capture(cfg: Config, to_stdout: bool, ui: str = "auto") -> int:
    reply = _send("capture", timeout=1.0)
    if reply is None:
        if _pick_ui(ui) == "qt":
            from .qt_app import run_once

            return run_once(cfg, to_stdout)
        return _standalone_capture(cfg, to_stdout)
    if not reply.get("ok"):
        print(f"daemon 拒绝执行：{reply}", file=sys.stderr)
        return 1
    return 0


def _standalone_capture(cfg: Config, to_stdout: bool) -> int:
    """daemon 不在时的一次性模式（会多花 ~0.5s 加载模型）。"""
    import threading

    from . import capture, gi_setup  # noqa: F401  (gi_setup 必须最先)
    from gi.repository import GLib, Gtk
    from .ocr import OcrEngine
    from .overlay import SelectionOverlay

    shot = capture.grab()
    engine = OcrEngine(cfg.ocr, cfg.post)
    state: dict[str, object] = {}

    def on_selected(x: int, y: int, w: int, h: int) -> None:
        crop = shot.bgr(x, y, w, h)

        def work() -> None:
            try:
                state["result"] = engine.recognize(crop)
            except Exception as exc:  # pragma: no cover - 环境相关
                state["error"] = str(exc)
            GLib.idle_add(Gtk.main_quit)

        threading.Thread(target=work, daemon=True).start()

    def on_cancel() -> None:
        Gtk.main_quit()

    overlay = SelectionOverlay(shot, cfg.ui, on_selected=on_selected, on_cancel=on_cancel)
    overlay.open(panel_x, panel_y)
    Gtk.main()

    if "error" in state:
        print(f"识别失败：{state['error']}", file=sys.stderr)
        return 1
    result = state.get("result")
    if result is None:
        return 0  # 用户取消
    if not result.text.strip():
        print("没有识别到文字", file=sys.stderr)
        return 1
    clipboard.copy(result.text, cfg.clipboard.also_primary)
    if to_stdout:
        print(result.text)
    return 0


# ---------------------------------------------------------------- status
def _cmd_status(cfg: Config) -> int:
    reply = _send("status", timeout=1.0)
    if reply is None:
        print("daemon 未运行")
        return 1
    print(json.dumps(reply, ensure_ascii=False, indent=2))
    pid = reply.get("pid")
    if isinstance(pid, int):
        rss = _rss_mb(pid)
        if rss:
            print(f"内存占用: {rss:.0f} MB (RSS)")
    return 0


def _cmd_stop() -> int:
    reply = _send("stop", timeout=2.0)
    print("已停止" if reply else "daemon 未运行")
    return 0 if reply else 1


# ---------------------------------------------------------------- doctor
def _cmd_doctor(cfg: Config) -> int:
    ok = True
    print(f"ocrsnip {__version__}")
    print(f"平台           : {sys.platform}")
    print(f"配置           : {config_path()} (存在={config_path().exists()})")
    print(f"日志           : {log_path()}")
    for warning in cfg.warnings:
        print(f"  ! {warning}")

    if is_windows() or _which_module("PySide6"):
        qt_ok = _doctor_qt(cfg)
        if is_windows():  # Linux 上 Qt 只是可选后端，坏了不影响 GTK 后端
            ok &= qt_ok
    if not is_windows():
        # 打包版只带 Qt（PyGObject/GTK 没法随包走），这时 GTK 那条"抓屏"检查必然失败，
        # 不该算进结论里——按实际选用的后端决定要不要查 GTK。
        ok &= _doctor_linux(cfg, need_gtk=_pick_ui("auto") == "gtk")

    daemon_reply = _send("status", timeout=0.5)
    if daemon_reply:
        print(
            f"运行中         : backend={daemon_reply.get('backend', 'gtk')} "
            f"预热={_fmt(daemon_reply.get('warm_ms'))} ms busy={daemon_reply.get('busy')}"
        )
        print(f"上次           : {daemon_reply.get('last')}")
        if daemon_reply.get("hotkey_error"):
            ok = False
            print(f"  ! 热键错误：{daemon_reply['hotkey_error']}")
    else:
        print("运行中         : 否")

    ok &= _doctor_ocr(cfg)
    print("结论           : " + ("就绪" if ok else "有问题，见上面标记 ! 的行"))
    return 0 if ok else 1


def _doctor_qt(cfg: Config) -> bool:
    try:
        from .qt_app import create_app, grab_screen

        create_app()
        from PySide6.QtGui import QCursor, QGuiApplication

        screens = QGuiApplication.screens()
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        print(f"显示器         : {len(screens)} 块，鼠标在 {screen.name()} dpr={screen.devicePixelRatio()}")
        started = time.perf_counter()
        pixmap, dpr = grab_screen(screen)
        print(
            f"抓屏           : {pixmap.width()}x{pixmap.height()} 物理像素，"
            f"{(time.perf_counter() - started) * 1000:.0f} ms"
        )
        from .geometry import panel_physical, panel_rect

        geo = screen.geometry()
        panel = panel_rect(
            (cursor.x(), cursor.y()),
            (geo.x(), geo.y(), geo.width(), geo.height()),
            scale=cfg.ui.panel_scale,
            min_size=(cfg.ui.panel_min_w, cfg.ui.panel_min_h),
            fullscreen=cfg.ui.fullscreen,
            size=(cfg.ui.panel_width, cfg.ui.panel_height),
        )
        print(f"面板           : {panel} → 物理 {panel_physical(panel, (geo.x(), geo.y()), dpr)}")
        return True
    except Exception as exc:
        print(f"Qt 后端        : 失败 {exc}")
        return False


def _doctor_linux(cfg: Config, need_gtk: bool = True) -> bool:
    ok = True
    from . import hotkey

    session = os.environ.get("XDG_SESSION_TYPE", "?")
    print(f"会话类型       : {session}  (X11 才能用内置全局热键)")
    if session != "x11":
        ok = False
        print("  ! 非 X11 会话：请改用桌面自定义快捷键调用 `ocrsnip capture`")

    if need_gtk:
        try:
            from . import capture, gi_setup  # noqa: F401
            from gi.repository import Gdk

            width, height = capture.screen_geometry()
            print(f"虚拟屏         : {width}x{height}  显示器={Gdk.Display.get_default().get_n_monitors()}")
            crop = capture.grab_region(0, 0, min(64, width), min(32, height)).bgr(0, 0, 64, 32)
            print(f"裁剪校验       : {crop.shape} dtype={crop.dtype}")
        except Exception as exc:
            ok = False
            print(f"抓屏           : 失败 {exc}")
    else:
        print("GTK 后端       : 跳过（当前是 Qt 后端，抓屏在上面测过）")

    print(f"xclip          : {'可用' if _which('xclip') else '缺失（剪贴板将退回 GTK）'}")
    print(f"xdotool        : {'可用' if _which('xdotool') else '缺失（auto_paste 不可用）'}")

    if _send("status", timeout=0.5):
        print(f"热键 {cfg.hotkey:<10s}: 由运行中的 daemon 持有（无需探测）")
    else:
        result = hotkey.probe(cfg.hotkey)
        print(f"热键 {cfg.hotkey:<10s}: {result}")
        ok = ok and result == "可用"
    return ok


def _doctor_ocr(cfg: Config) -> bool:
    try:
        import numpy as np

        from .ocr import OcrEngine

        engine = OcrEngine(cfg.ocr, cfg.post)
        started = time.perf_counter()
        engine.warmup()
        warm_ms = (time.perf_counter() - started) * 1000
        img = np.full((120, 640, 3), 255, dtype=np.uint8)
        img[40:70, 20:600] = 0
        started = time.perf_counter()
        engine.recognize(img)
        first_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        engine.recognize(img)
        second_ms = (time.perf_counter() - started) * 1000
        print(f"OCR 预热       : {warm_ms:.0f} ms（含模型加载）")
        print(f"OCR 单次       : {first_ms:.0f} ms / {second_ms:.0f} ms（640x120）")
        return True
    except Exception as exc:
        print(f"OCR            : 失败 {exc}")
        return False


# ---------------------------------------------------------------- selftest
def _save_last_png(png: bytes) -> None:
    """每次选区都留一份图在固定路径，想"要图不要字"时直接取。"""
    try:
        path = last_png_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    except OSError:
        pass


def _maybe_save_debug_png(frame, x0: int, y0: int, x1: int, y1: int) -> None:
    """OCRSNIP_DEBUG_PNG=<path> 时把选区图存下来（验收/排错用）。"""
    target = os.environ.get("OCRSNIP_DEBUG_PNG")
    if not target:
        return
    try:
        frame.to_pil(x0, y0, x1, y1).save(target)
    except Exception:
        pass


def _cmd_selftest(cfg: Config, ui: str = "auto") -> int:
    """装完先跑这个：不依赖截图/热键，直接验证 OCR 能不能出字。"""
    _setup_logging(cfg)
    backend = _pick_ui(ui)
    print(f"ocrsnip {__version__} selftest（backend={backend}）")
    ok = True

    app = None
    if backend == "qt":
        try:
            from .qt_app import create_app

            app = create_app()  # 必须先有 QGuiApplication，画字和剪贴板都要它
            from PySide6.QtGui import QGuiApplication

            print(f"  显示器      : {len(QGuiApplication.screens())} 块")
        except Exception as exc:
            ok = False
            print(f"  Qt 失败     : {exc}")

    try:
        import numpy as np

        from .ocr import OcrEngine

        engine = OcrEngine(cfg.ocr, cfg.post)
        started = time.perf_counter()
        engine.warmup()
        warm_ms = (time.perf_counter() - started) * 1000
        image = _selftest_image() if (app is not None) else None
        if image is None:
            image = np.full((90, 420, 3), 255, dtype=np.uint8)  # 纯色图：只测通路
        started = time.perf_counter()
        result = engine.recognize(image)
        ocr_ms = (time.perf_counter() - started) * 1000
        print(f"  预热        : {warm_ms:.0f} ms")
        print(f"  识别        : {ocr_ms:.0f} ms，{result.chars} 字")
        if result.text:
            print(f"  文本        : {result.text!r}")
    except Exception as exc:
        ok = False
        print(f"  OCR 失败    : {exc}")

    if app is not None:
        try:
            from PySide6.QtGui import QGuiApplication

            clipboard = QGuiApplication.clipboard()
            clipboard.setText("ocrsnip-selftest")
            good = clipboard.text() == "ocrsnip-selftest"
            ok &= good
            print(f"  剪贴板      : {'可用' if good else '不可用'}")
        except Exception as exc:
            ok = False
            print(f"  剪贴板失败  : {exc}")

    print("结论           : " + ("通过" if ok else "失败"))
    return 0 if ok else 1


def _selftest_image():
    """用 Qt 现画一张带中文的图（不依赖 PIL 字体，Windows 上一定有字体）。"""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QImage, QPainter

        from .qt_app import qimage_to_bgr

        image = QImage(460, 90, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setPen(QColor("black"))
        font = QFont()
        font.setPointSize(20)
        painter.setFont(font)
        painter.drawText(12, 55, "ocrsnip 自检 OCR 1234")
        painter.end()
        return qimage_to_bgr(image)
    except Exception:
        return None


# ---------------------------------------------------------------- config
def _cmd_config(cfg: Config, args) -> int:
    path = config_path()
    if args.init:
        if path.exists():
            print(f"已存在，未覆盖：{path}")
            return 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
        print(f"已写入 {path}")
        return 0
    print(f"配置路径: {path} (存在={path.exists()})")
    if not args.init:
        from dataclasses import asdict

        print(json.dumps(asdict(cfg), ensure_ascii=False, indent=2, default=str))
    return 0


# ---------------------------------------------------------------- helpers
def _warn(text: str) -> None:
    """窗口化程序没有控制台，警告要进日志。"""
    logging.getLogger("ocrsnip").warning(text)
    if sys.stderr is not None:
        try:
            print(f"[ocrsnip] {text}", file=sys.stderr)
        except Exception:
            pass


def _fmt(value) -> str:
    return "?" if value is None else f"{float(value):.0f}"


def _setup_logging(cfg: Config) -> None:
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = []
    try:
        handlers.append(logging.FileHandler(log_path(), encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers or None,
        force=True,
    )
    logging.getLogger("ocrsnip").debug("日志文件: %s", log_path())


def _send(command: str, timeout: float = 1.0) -> dict | None:
    """先试 unix socket（Linux GTK 后端），再试 QLocalSocket（Qt 后端，两平台通用）。"""
    reply = _send_unix(command, timeout)
    if reply is not None:
        return reply
    return _send_qt(command, timeout)


def _send_unix(command: str, timeout: float) -> dict | None:
    if is_windows():
        return None
    path = socket_path()
    if not Path(path).exists():
        return None
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(path))
        client.sendall((command + "\n").encode())
        chunks = []
        while True:
            data = client.recv(65536)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        payload = b"".join(chunks).decode("utf-8", "replace").strip()
        return json.loads(payload) if payload else None
    except (OSError, json.JSONDecodeError):
        return None
    finally:
        client.close()


def _send_qt(command: str, timeout: float) -> dict | None:
    if not _which_module("PySide6"):
        return None
    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtNetwork import QLocalSocket

        # QLocalSocket 需要 Qt 应用实例，否则 waitForConnected 直接失败
        _app = QCoreApplication.instance() or QCoreApplication([])
        socket_ = QLocalSocket()
        socket_.connectToServer(ipc_name())
        if not socket_.waitForConnected(int(timeout * 1000)):
            return None
        socket_.write((command + "\n").encode())
        socket_.flush()
        socket_.waitForBytesWritten(int(timeout * 1000))
        data = b""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and b"\n" not in data:
            if socket_.waitForReadyRead(200):
                data += bytes(socket_.readAll())
            elif socket_.state() != socket_.state().ConnectedState:
                break
        socket_.disconnectFromServer()
        payload = data.decode("utf-8", "replace").strip()
        return json.loads(payload) if payload else None
    except Exception:
        return None


def _rss_mb(pid: int) -> float | None:
    """进程常驻内存（Linux 读 /proc，Windows 走 GetProcessMemoryInfo）。"""
    if is_windows():
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return None
            try:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                if psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    return counters.WorkingSetSize / (1024 * 1024)
                return None
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def _which(exe: str) -> bool:
    import shutil

    return shutil.which(exe) is not None


def _which_module(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
