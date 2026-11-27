"""Qt 后端：Windows（也可在 Linux 上跑，用于自动化测试）。

与 GTK/X11 后端（daemon.py）的差异集中在这里：

| 能力 | Windows / Qt | Linux / GTK 后端 |
| --- | --- | --- |
| 全局热键 | `RegisterHotKey`（win_hotkey.py） | X11 `XGrabKey`（hotkey.py） |
| 抓屏 | `QScreen.grabWindow` 逐屏抓，按 devicePixelRatio 换算 | `Gdk.pixbuf_get_from_window` |
| 浮层 | QWidget 无边框置顶 | Gtk.Window + cairo |
| 剪贴板 | Qt（进程常驻即托管） | xclip 优先 |
| 单实例 / IPC | `QLocalServer` | unix socket |
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QScreen,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from .config import Config, ipc_name
from .geometry import panel_physical, panel_rect
from .mem import MemoryProbe
from .ocr import OcrEngine, OcrResult

log = logging.getLogger("ocrsnip")

APP_NAME = "ocrsnip"


# --------------------------------------------------------------------- 图像
def qimage_to_bgr(image: QImage) -> np.ndarray:
    """QImage → rapidocr 需要的 BGR ndarray。

    Format_RGB32 在内存里是小端 BGRA，所以取前三个通道正好就是 BGR，不需要翻转。
    """
    if image.format() != QImage.Format.Format_RGB32:
        image = image.convertToFormat(QImage.Format.Format_RGB32)
    width, height = image.width(), image.height()
    data = image.constBits()
    array = np.frombuffer(data, dtype=np.uint8).reshape(
        height, image.bytesPerLine() // 4, 4
    )[:, :width, :3]
    return np.ascontiguousarray(array)


def grab_screen(screen: QScreen) -> tuple[QPixmap, float]:
    """抓一块屏幕，返回（物理像素 pixmap, devicePixelRatio）。"""
    pixmap = screen.grabWindow(0)
    dpr = float(screen.devicePixelRatio() or 1.0)
    pixmap.setDevicePixelRatio(1.0)  # 这里按物理像素用，绘制前再设回去
    return pixmap, dpr


# --------------------------------------------------------------------- 浮层
class OverlayWindow(QWidget):
    """面板式框选浮层：不透明窗口 + 冻结画面 + 橡皮筋。"""

    def __init__(self, panel_pixmap: QPixmap, dpr: float, cfg, on_done, on_cancel):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.cfg = cfg
        self._dpr = dpr
        self._raw = panel_pixmap  # 物理像素，用于裁剪
        self._view = QPixmap(panel_pixmap)  # 隐式共享，仅用于 1:1 绘制
        self._view.setDevicePixelRatio(dpr)
        self._on_done = on_done
        self._on_cancel = on_cancel
        self._origin = None
        self._sel: QRect | None = None
        self._finished = False

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowTitle("ocrsnip-overlay")
        self._accent = QColor(cfg.accent)

        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._cancel)
        self._timeout.start(int(cfg.overlay_timeout_sec * 1000))

    # ---- 生命周期 ----------------------------------------------------
    def open_at(self, x: int, y: int, width: int, height: int) -> None:
        self.setGeometry(x, y, width, height)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _finish(self, rect: QRect | None) -> None:
        if self._finished:
            return
        self._finished = True
        self._timeout.stop()
        self.hide()
        try:
            self.close()
            self.deleteLater()
        except Exception:
            pass
        if rect is None:
            self._on_cancel()
        else:
            self._on_done(rect)

    def _cancel(self) -> None:
        self._finish(None)

    # ---- 事件 --------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            self._cancel()
            return
        self._origin = event.position().toPoint()
        self._sel = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is None:
            return
        old = self._sel
        self._sel = QRect(self._origin, event.position().toPoint()).normalized()
        self.update(self._damage(old, self._sel))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._origin is None or event.button() != Qt.MouseButton.LeftButton:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        self._origin = None
        if rect.width() < self.cfg.min_crop_px or rect.height() < self.cfg.min_crop_px:
            self._cancel()
            return
        self._finish(rect)

    @staticmethod
    def _damage(old: QRect | None, new: QRect | None) -> QRect:
        """只重绘选区变化的那点面积，大屏拖拽也不掉帧。"""
        rect = QRect()
        for item in (old, new):
            if item is not None:
                rect = rect.united(item.adjusted(-3, -3, 3, 3))
        return rect

    # ---- 绘制 --------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.drawPixmap(0, 0, self._view)

        dim = QColor(0, 0, 0, int(self.cfg.dim * 255))
        sel = self._sel
        if sel is not None and sel.width() > 0 and sel.height() > 0:
            size = self.size()
            for rect in (
                QRect(0, 0, size.width(), sel.top()),
                QRect(0, sel.bottom() + 1, size.width(), size.height() - sel.bottom() - 1),
                QRect(0, sel.top(), sel.left(), sel.height()),
                QRect(sel.right() + 1, sel.top(), size.width() - sel.right() - 1, sel.height()),
            ):
                painter.fillRect(rect, dim)
            painter.setPen(QPen(self._accent, 1))
            painter.drawRect(sel.adjusted(0, 0, -1, -1))
            self._draw_label(painter, sel)
        else:
            painter.fillRect(self.rect(), dim)
            painter.setPen(QPen(QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 140), 1))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
            if self.cfg.show_hint:
                self._draw_hint(painter)

    def _draw_label(self, painter: QPainter, sel: QRect) -> None:
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        text = f"{sel.width()} × {sel.height()}"
        metrics = painter.fontMetrics()
        box = QRect(
            sel.left() + 6,
            max(6, sel.top() - metrics.height() - 10),
            metrics.horizontalAdvance(text) + 10,
            metrics.height() + 6,
        )
        painter.fillRect(box, QColor(20, 20, 25, 210))
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(box.adjusted(5, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def _draw_hint(self, painter: QPainter) -> None:
        font = QFont()
        font.setPointSize(11)
        painter.setFont(font)
        text = "拖动框选  ·  Esc / 右键取消"
        metrics = painter.fontMetrics()
        box = QRect(
            (self.width() - metrics.horizontalAdvance(text)) // 2 - 14,
            40,
            metrics.horizontalAdvance(text) + 28,
            metrics.height() + 16,
        )
        painter.fillRect(box, QColor(20, 20, 25, 190))
        painter.setPen(QColor(255, 255, 255, 245))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


# --------------------------------------------------------------------- Toast
class ToastWindow(QWidget):
    def __init__(self, text: str, duration_ms: int, error: bool = False):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._text = text
        self._error = error
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        metrics = self.fontMetrics()
        width = metrics.horizontalAdvance(text) + 32
        height = metrics.height() + 20
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.setGeometry(
            geo.x() + (geo.width() - width) // 2,
            geo.y() + geo.height() - height - 90,
            width,
            height,
        )
        QTimer.singleShot(max(200, duration_ms), self.close)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(190, 45, 45, 235) if self._error else QColor(28, 28, 33, 235)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.setPen(QColor(255, 255, 255, 245))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)


# --------------------------------------------------------------------- 热键
class HotkeyBridge(QObject):
    triggered = Signal()

    def __init__(self):
        super().__init__()
        self._impl = None
        self._error: str | None = None

    def start(self, spec: str) -> None:
        callback = self.triggered.emit  # 从工作线程 emit，Qt 会自动排队到主线程
        if sys.platform == "win32":
            from .win_hotkey import WinHotkey

            self._impl = WinHotkey(spec, callback)
        else:
            from .hotkey import HotkeyListener

            self._impl = HotkeyListener(spec, callback)
        try:
            self._impl.start()
        except Exception as exc:
            self._error = str(exc)
            raise

    @property
    def error(self) -> str | None:
        return self._error

    def stop(self) -> None:
        if self._impl is not None:
            try:
                self._impl.stop()
            except Exception:
                pass


# --------------------------------------------------------------------- 应用
class OcrWorker(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: OcrEngine):
        super().__init__()
        self._engine = engine
        self._lock = threading.Lock()

    def submit(self, bgr: np.ndarray) -> None:
        threading.Thread(target=self._run, args=(bgr,), daemon=True).start()

    def _run(self, bgr: np.ndarray) -> None:
        try:
            with self._lock:
                result: OcrResult = self._engine.recognize(bgr)
        except Exception as exc:  # pragma: no cover - 环境相关
            log.exception("识别失败")
            self.failed.emit(str(exc))
            return
        self.done.emit(result)


class QtBackend:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.engine = OcrEngine(cfg.ocr, cfg.post)
        self.worker = OcrWorker(self.engine)
        self.hotkey = HotkeyBridge()
        self.server: QLocalServer | None = None
        self.tray: QSystemTrayIcon | None = None
        self.overlay: OverlayWindow | None = None
        self._busy = False
        self._shot: QPixmap | None = None
        self._pending_png: bytes | None = None
        self._pending_dib: bytes | None = None
        self._dpr = 1.0
        self._panel = (0, 0, 0, 0)
        self.last: dict[str, object] = {}
        self._warm_ms: float | None = None
        self._mem = MemoryProbe()

    # ---- 启动 --------------------------------------------------------
    def run(self) -> int:
        self._make_tray()
        self.worker.done.connect(self._deliver)
        self.worker.failed.connect(self._failed)

        self.hotkey.triggered.connect(self.trigger)
        try:
            self.hotkey.start(self.cfg.hotkey)
            log.info("热键已注册：%s", self.cfg.hotkey)
        except Exception as exc:
            log.error("热键不可用：%s", exc)
            self._toast(f"热键 {self.cfg.hotkey} 不可用：{exc}", error=True)

        if not self._listen():
            log.info("已有实例在运行，转发 capture 后退出")
            return 0

        threading.Thread(target=self._warmup, name="ocrsnip-warmup", daemon=True).start()
        return QApplication.instance().exec()

    def _warmup(self) -> None:
        started = time.perf_counter()
        try:
            self.engine.warmup()
            self._warm_ms = (time.perf_counter() - started) * 1000
            log.info("OCR 引擎预热完成：%.0f ms", self._warm_ms)
        except Exception as exc:  # pragma: no cover
            log.exception("预热失败: %s", exc)

    def _make_tray(self) -> None:
        icon = QIcon(_tray_icon_pixmap())
        self.tray = QSystemTrayIcon(icon)
        menu = QMenu()
        menu.addAction(f"立即截屏（{self.cfg.hotkey}）", self.trigger)
        menu.addAction("打开配置文件", _open_config)
        menu.addSeparator()
        menu.addAction("退出", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(f"ocrsnip · {self.cfg.hotkey}")
        self.tray.show()

    def _listen(self) -> bool:
        name = ipc_name()
        if self._forward_to_existing(name):
            return False
        # 上一次崩溃会留下 socket 文件，QLocalServer 不会自动清理，必须先删
        QLocalServer.removeServer(name)
        self.server = QLocalServer()
        if not self.server.listen(name):
            log.error("单实例监听失败：%s（%s）", name, self.server.errorString())
            return False
        self.server.newConnection.connect(self._on_connection)
        return True

    @staticmethod
    def _forward_to_existing(name: str) -> bool:
        """已有实例就转发一次 capture 并返回 True。"""
        socket = QLocalSocket()
        socket.connectToServer(name)
        if not socket.waitForConnected(300):
            return False
        socket.write(b"capture\n")
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        log.info("已有实例在运行，已转发 capture")
        return True

    def _on_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        buffer = bytearray()

        def pump(retries: int = 0) -> None:
            # 客户端连上就写，可能早于 readyRead 的连接；既读现成数据，也做几次重试
            try:
                buffer.extend(bytes(socket.readAll()))
            except (RuntimeError, AttributeError):
                return  # 套接字已被销毁（客户端提前断开）
            if b"\n" in buffer:
                command = bytes(buffer).split(b"\n", 1)[0].decode("utf-8", "replace").strip()
                self._handle_command(socket, command)
            elif retries < 25:
                QTimer.singleShot(20, lambda: pump(retries + 1))

        socket.readyRead.connect(lambda: pump(25))
        QTimer.singleShot(0, pump)
        socket.disconnected.connect(socket.deleteLater)

    def _handle_command(self, socket: QLocalSocket, command: str) -> None:
        if command == "capture":
            self.trigger()
            reply = {"ok": True, "action": "capture"}
        elif command == "status":
            reply = {
                "ok": True,
                "backend": "qt",
                "pid": os.getpid(),
                "hotkey": self.cfg.hotkey,
                "warm_ms": self._warm_ms,
                "busy": self._busy,
                "last": self.last,
                "warnings": self.cfg.warnings,
                "hotkey_error": self.hotkey.error,
            }
        elif command == "quit":
            reply = {"ok": True, "action": "quit"}
            QTimer.singleShot(100, self.quit)
        else:
            reply = {"ok": False, "error": f"未知指令: {command}"}
        import json

        socket.write((json.dumps(reply, ensure_ascii=False) + "\n").encode())
        socket.flush()
        socket.disconnectFromServer()

    def quit(self) -> None:
        try:
            self.hotkey.stop()
        except Exception:
            pass
        if self.tray is not None:
            self.tray.hide()
        QApplication.instance().quit()

    # ---- 主流程 ------------------------------------------------------
    def trigger(self) -> None:
        if self._busy:
            log.debug("上一次还没结束，忽略本次触发")
            return
        self._busy = True

        started = time.perf_counter()

        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        panel = panel_rect(
            (cursor.x(), cursor.y()),
            (geo.x(), geo.y(), geo.width(), geo.height()),
            scale=self.cfg.ui.panel_scale,
            min_size=(self.cfg.ui.panel_min_w, self.cfg.ui.panel_min_h),
            fullscreen=self.cfg.ui.fullscreen,
            size=(self.cfg.ui.panel_width, self.cfg.ui.panel_height),
        )
        try:
            full, dpr = grab_screen(screen)
            px, py, pw, ph = panel_physical(panel, (geo.x(), geo.y()), dpr)
            self._shot = full.copy(px, py, pw, ph)
            self._shot.setDevicePixelRatio(1.0)
            self._dpr = dpr
            self._panel = panel

            self.overlay = OverlayWindow(
                self._shot, dpr, self.cfg.ui, on_done=self._on_selected, on_cancel=self._on_cancel
            )
            self.overlay.open_at(panel[0], panel[1], panel[2], panel[3])
            self.last = {
                "panel": list(panel),
                "pointer": [cursor.x(), cursor.y()],
                "dpr": dpr,
                "overlay_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        except Exception as exc:
            log.exception("截屏失败")
            self.overlay = None
            self._busy = False
            self._toast(f"截屏失败：{exc}", error=True)

    def _on_cancel(self) -> None:
        log.debug("已取消")
        self.overlay = None
        self._shot = None
        self._busy = False

    def _on_selected(self, rect: QRect) -> None:
        shot, dpr = self._shot, self._dpr
        panel = self._panel
        self.overlay = None
        self._shot = None
        if shot is None:
            self._on_cancel()
            return
        px, py, pw, ph = panel_physical(
            (rect.x(), rect.y(), rect.width(), rect.height()), (0, 0), dpr
        )
        crop = shot.copy(px, py, pw, ph).toImage()
        bgr = qimage_to_bgr(crop)
        self.last["rect"] = [panel[0] + rect.x(), panel[1] + rect.y(), rect.width(), rect.height()]
        self.worker.submit(bgr)

    # ---- 结果 --------------------------------------------------------
    def _deliver(self, result: OcrResult) -> None:
        self._busy = False
        if not result.text.strip():
            log.info("没识别到文字（%.0f ms）", result.elapsed_ms)
            self._toast("没有识别到文字", error=True)
            self.last["chars"] = 0
            self._mem.tick("识别")
            return
        backend = self._copy_result(result.text)
        self.last["clipboard"] = backend
        if self.cfg.clipboard.auto_paste:
            QTimer.singleShot(int(result.elapsed_ms), _send_ctrl_v)
        self.last.update(
            {"ocr_ms": round(result.elapsed_ms, 1), "chars": result.chars, "lines": len(result.lines)}
        )
        log.info("已复制 %d 字（%d 行，%.0f ms）", result.chars, len(result.lines), result.elapsed_ms)
        self._toast(f"已复制 {result.chars} 字 · {result.elapsed_ms:.0f} ms")
        self._mem.tick("识别")

    def _copy_result(self, text: str) -> str:
        """Windows：一次放 text + PNG + CF_DIB（对应 X11 的多 target）。"""
        png, dib = self._pending_png, self._pending_dib
        self._pending_png = self._pending_dib = None
        if self.cfg.clipboard.copy_image:   # 只要图片
            text = None
        if sys.platform == "win32" and (png or dib):
            try:
                from . import win_clipboard

                result = win_clipboard.copy(text=text, png=png, dib=dib)
                if result != "none":
                    return f"win:{result}"
            except Exception as exc:  # pragma: no cover
                log.warning("多格式剪贴板失败，退回 Qt: %s", exc)
        if text:
            QGuiApplication.clipboard().setText(text)
            return "qt-text"
        return "none"

    def _failed(self, message: str) -> None:
        self._busy = False
        self._toast(f"识别失败：{message}", error=True)

    def _toast(self, text: str, error: bool = False) -> None:
        if not self.cfg.ui.show_toast:
            return
        toast = ToastWindow(text, self.cfg.ui.toast_ms, error)
        toast.show()
        self._toasts = [item for item in getattr(self, "_toasts", []) if item.isVisible()]
        self._toasts.append(toast)


# --------------------------------------------------------------------- 杂项
def _tray_icon_pixmap() -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor(61, 174, 233))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QPen(QColor(255, 255, 255), 6))
    painter.drawRect(16, 20, 32, 24)
    painter.drawLine(22, 16, 22, 20)
    painter.drawLine(42, 16, 42, 20)
    painter.end()
    return pixmap


def _open_config() -> None:
    from .config import config_path

    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        from .config import DEFAULT_CONFIG_TOML

        path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606
    else:
        os.system(f'xdg-open "{path}" &')


def _send_ctrl_v() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL, VK_V = 0x11, 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def run_once(cfg: Config, to_stdout: bool = False) -> int:
    """daemon 没在跑时的一次性模式：只截一次图、识别一次、写剪贴板。"""
    app = create_app()
    backend = QtBackend(cfg)
    state: dict[str, object] = {}
    original_deliver = backend._deliver

    def deliver(result):
        state["result"] = result
        original_deliver(result)
        QTimer.singleShot(50, app.quit)

    backend._deliver = deliver  # type: ignore[method-assign]
    backend.hotkey = None  # 一次性模式不需要全局热键
    backend.worker.done.connect(deliver, Qt.ConnectionType.UniqueConnection)
    backend.trigger()
    app.exec()

    result = state.get("result")
    if result is None:
        return 0
    if not getattr(result, "text", "").strip():
        return 1
    if to_stdout:
        print(result.text)
    return 0


def create_app() -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # 托盘常驻
    return app
