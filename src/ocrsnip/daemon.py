"""常驻守护进程：热键 → 抓屏 → 框选 → OCR → 剪贴板。

模型常驻内存，所以每次截屏只有"抓屏 + 推理"两段耗时。
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import signal
import socketserver
import threading
import time
from pathlib import Path

from . import display_env
from .geometry import panel_rect
from .mem import MemoryProbe

from .config import is_windows

from . import capture, clipboard, gi_setup, hotkey  # noqa: F401  (gi_setup 必须最先；GTK 初始化依赖 DISPLAY 已确定)
from gi.repository import GLib, Gtk
from .config import Config, last_png_path, socket_path
from .ocr import OcrEngine, OcrResult
from .overlay import SelectionOverlay
from .toast import Toast

log = logging.getLogger("ocrsnip")


class Daemon:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.engine = OcrEngine(cfg.ocr, cfg.post)
        self._lock = threading.Lock()
        self._overlay: SelectionOverlay | None = None
        self._shot: capture.ScreenShot | None = None
        # 在途次数：一次截屏从触发到"复制/取消"正好 +1 -1。
        # 用计数器而不是布尔，是为了任何一条路径漏复位都不会永久卡死。
        self._inflight = 0
        self._inflight_since = 0.0
        self._lock_file = None
        self._server: socketserver.UnixStreamServer | None = None
        self._hotkey: hotkey.HotkeyListener | None = None
        self._warm_ms: float | None = None
        self._mem = MemoryProbe()
        self._pending_png: bytes | None = None
        self.last: dict[str, object] = {}

    # ---- 启动 --------------------------------------------------------
    def run(self) -> int:
        # 登录自启时 DISPLAY 可能还没进 systemd 环境，先自己找一下
        if not display_env.ensure_display():
            print("[ocrsnip] 没有可用的 X11 显示，退出")
            return 1
        time.sleep(0)  # 让日志顺序稳定

        sock_path = socket_path()
        if not self._acquire_singleton(sock_path):
            print("ocrsnip daemon 已在运行")
            return 0

        log.info(
            "屏幕 %sx%s，热键 %s", *capture.screen_geometry(), self.cfg.hotkey
        )
        self._start_socket(sock_path)
        self._start_hotkey()
        self._start_warmup()

        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._quit)

        Gtk.main()
        self._cleanup(sock_path)
        return 0

    def _acquire_singleton(self, sock_path: Path) -> bool:
        lock_file = sock_path.with_suffix(".lock")
        self._lock_file = open(lock_file, "w")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        sock_path.unlink(missing_ok=True)
        return True

    def _start_socket(self, sock_path: Path) -> None:
        daemon = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                line = self.rfile.readline().decode("utf-8", "replace").strip()
                reply = daemon.handle_command(line)
                self.wfile.write((json.dumps(reply, ensure_ascii=False) + "\n").encode())

        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True
            allow_reuse_address = True

        self._server = Server(str(sock_path), Handler)
        os.chmod(sock_path, 0o600)
        threading.Thread(target=self._server.serve_forever, name="ocrsnip-ipc", daemon=True).start()

    def _start_hotkey(self) -> None:
        self._hotkey = hotkey.HotkeyListener(self.cfg.hotkey, self._hotkey_pressed)
        try:
            self._hotkey.start()
            log.info("热键已注册：%s", self.cfg.hotkey)
        except hotkey.HotkeyUnavailable as exc:
            log.error("热键不可用：%s", exc)
            print(f"[ocrsnip] 热键不可用：{exc}")

    def _start_warmup(self) -> None:
        def work() -> None:
            started = time.perf_counter()
            try:
                self.engine.warmup()
                self._warm_ms = (time.perf_counter() - started) * 1000
                log.info("OCR 引擎预热完成：%.0f ms", self._warm_ms)
            except Exception as exc:  # pragma: no cover - 环境相关
                log.exception("OCR 预热失败: %s", exc)

        threading.Thread(target=work, name="ocrsnip-warmup", daemon=True).start()

    # ---- 指令 --------------------------------------------------------
    def handle_command(self, line: str) -> dict:
        cmd = line.split()[0] if line else "ping"
        if cmd == "capture":
            GLib.idle_add(self.trigger)
            return {"ok": True, "action": "capture"}
        if cmd == "stop":
            GLib.idle_add(self._quit)
            return {"ok": True, "action": "stop"}
        if cmd in ("status", "ping"):
            return {
                "ok": True,
                "pid": os.getpid(),
                "hotkey": self.cfg.hotkey,
                "screen": capture.screen_geometry(),
                "warm_ms": self._warm_ms,
                "busy": self._inflight > 0,
                "last": self.last,
                "warnings": self.cfg.warnings,
            }
        return {"ok": False, "error": f"未知指令: {cmd}"}

    def _quit(self) -> bool:
        Gtk.main_quit()
        return False

    # ---- 主流程 ------------------------------------------------------
    def _hotkey_pressed(self) -> None:
        GLib.idle_add(self.trigger)

    def trigger(self) -> bool:
        if self._inflight:
            # 兜底：正常路径都会复位，真卡住超过 2 分钟就强行放开，避免"热键突然没反应"
            if self._overlay is None and time.monotonic() - self._inflight_since > 120:
                log.warning("上一次截屏卡住超过 120s，强制复位")
                self._inflight = 0
            else:
                log.debug("上一次还没结束（%d 在途），忽略本次触发", self._inflight)
                return False
        self._inflight += 1
        self._inflight_since = time.monotonic()

        try:
            started = time.perf_counter()
            px, py = capture.pointer_position()
            panel = panel_rect(
                (px, py),
                capture.monitor_at(px, py),
                scale=self.cfg.ui.panel_scale,
                min_size=(self.cfg.ui.panel_min_w, self.cfg.ui.panel_min_h),
                fullscreen=self.cfg.ui.fullscreen,
                size=(self.cfg.ui.panel_width, self.cfg.ui.panel_height),
            )
            panel_x, panel_y, panel_w, panel_h = panel
            # 只抓面板这一小块：比抓全屏快，且不会和窗口管理器抢整屏
            self._shot = capture.grab_region(panel_x, panel_y, panel_w, panel_h)
            grab_ms = (time.perf_counter() - started) * 1000
            self._overlay = SelectionOverlay(
                self._shot,
                self.cfg.ui,
                on_selected=self._on_selected,
                on_cancel=self._on_cancel,
            )
            self._overlay.open(panel_x, panel_y)
            open_ms = (time.perf_counter() - started) * 1000
            log.debug("选区后端=panel(GTK 冻结画面), 面板 %s 抓屏 %.0f ms，浮层就绪 %.0f ms", panel, grab_ms, open_ms)
            self.last = {
                "panel": panel,
                "pointer": (px, py),
                "grab_ms": round(grab_ms, 1),
                "overlay_ms": round(open_ms, 1),
            }
        except Exception as exc:
            log.exception("截屏失败: %s", exc)
            self._overlay = None
            self._release()
            self._toast(f"截屏失败：{exc}", error=True)
        return False

    def _on_cancel(self) -> None:
        log.info("已取消")
        self._overlay = None
        self._shot = None
        self._release()

    def _release(self) -> None:
        if self._inflight > 0:
            self._inflight -= 1

    def _on_selected(self, x: int, y: int, w: int, h: int) -> None:
        """x/y 是面板内坐标，加 origin 换成屏幕坐标。"""
        shot = self._shot
        self._overlay = None
        if shot is None:
            self._on_cancel()
            return
        crop = shot.bgr(x, y, w, h)
        screen_rect = (shot.origin_x + x, shot.origin_y + y, w, h)
        self._shot = None
        threading.Thread(
            target=self._recognize,
            args=(crop, screen_rect),
            name="ocrsnip-ocr",
            daemon=True,
        ).start()

    def _recognize(self, crop, rect: tuple[int, int, int, int]) -> None:
        try:
            with self._lock:
                result: OcrResult = self.engine.recognize(crop)
        except Exception as exc:  # pragma: no cover - 环境相关
            log.exception("识别失败: %s", exc)
            GLib.idle_add(self._finish_error, str(exc))
            return
        GLib.idle_add(self._deliver, result, rect)

    def _deliver(self, result: OcrResult, rect: tuple[int, int, int, int]) -> bool:
        if not result.text.strip():
            log.info("没识别到文字（%.0f ms，选区 %s）", result.elapsed_ms, rect)
            self._mem.tick("识别")
            self._release()
            self._toast("没有识别到文字", error=True)
            self.last = {"ocr_ms": round(result.elapsed_ms, 1), "chars": 0}
            return False

        backend = self._copy_result(result.text)
        self._pending_png = None
        if self.cfg.clipboard.auto_paste:
            GLib.timeout_add(int(result.elapsed_ms), self._auto_paste)
        self.last = {
            "ocr_ms": round(result.elapsed_ms, 1),
            "chars": result.chars,
            "lines": len(result.lines),
            "rect": rect,
            "clipboard": backend,
        }
        log.info(
            "已复制 %d 字（%d 行，%.0f ms）",
            result.chars,
            len(result.lines),
            result.elapsed_ms,
        )
        self._toast(f"已复制 {result.chars} 字 · {result.elapsed_ms:.0f} ms")
        self._mem.tick("识别")
        self._release()
        return False

    def _copy_result(self, text: str) -> str:
        """X11：一个 owner 同时提供 text 与 image/png；其它平台走原路径。"""
        png = self._pending_png
        if is_windows():
            if self.cfg.clipboard.copy_image:
                return "image"
            return clipboard.copy(text, self.cfg.clipboard.also_primary)
        try:
            from . import x11_clip as x11clip

            ok = x11clip.spawn(text=None if self.cfg.clipboard.copy_image else text, png=png)
            if ok:
                return "x11:text+image" if text and png else "x11:one"
        except Exception as exc:  # pragma: no cover - 环境相关
            log.warning("多格式剪贴板失败，退回 xclip: %s", exc)
        if self.cfg.clipboard.copy_image:
            return "image"
        return clipboard.copy(text, self.cfg.clipboard.also_primary)

    def _auto_paste(self) -> bool:
        clipboard.paste()
        return False

    def _finish_error(self, message: str) -> bool:
        self._release()
        self._toast(f"识别失败：{message}", error=True)
        return False

    def _toast(self, text: str, error: bool = False) -> None:
        if not self.cfg.ui.show_toast:
            return
        toast = Toast(text, duration_ms=self.cfg.ui.toast_ms, error=error)
        toast.show_briefly()

    def _cleanup(self, sock_path: Path) -> None:
        if self._hotkey is not None:
            self._hotkey.stop()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        sock_path.unlink(missing_ok=True)
        if self._lock_file is not None:
            self._lock_file.close()
