"""框选浮层：整屏"冻结"截图 + 压暗 + 橡皮筋框选。

性能要点：
- 窗口本身是不透明的，直接画抓到的截图，不依赖合成器的 alpha；
- 拖动时只让 GTK 重绘脏矩形（queue_draw_area），大屏也不掉帧。
"""

from __future__ import annotations

from typing import Callable

from . import gi_setup  # noqa: F401  (必须先于其它 gi 导入)
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from .capture import ScreenShot
from .config import UiConfig


class SelectionOverlay(Gtk.Window):
    def __init__(
        self,
        shot: ScreenShot,
        cfg: UiConfig,
        on_selected: Callable[[int, int, int, int], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.shot = shot
        self.cfg = cfg
        self._on_selected = on_selected
        self._on_cancel = on_cancel
        self._start: tuple[int, int] | None = None
        self._sel: tuple[int, int, int, int] | None = None
        self._done = False
        self._timeout_id = 0

        self.set_title("ocrsnip-overlay")
        self.set_decorated(False)
        # 注意：不能 set_resizable(False)。GTK 会忽略之后的所有程序化 resize，
        # 窗口就停留在默认 200x200 —— 这正是"浮层只出现在左上角一小块"的根因。
        self.set_resizable(True)
        self.set_default_size(shot.width, shot.height)
        self.set_size_request(shot.width, shot.height)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        self.set_focus_on_map(True)
        self.set_app_paintable(False)
        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        self.connect("draw", self._on_draw)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("key-press-event", self._on_key)
        self.connect("destroy", self._on_destroy)

    # ---- 生命周期 ----------------------------------------------------
    def open(self, x: int = 0, y: int = 0) -> None:
        self.move(x, y)
        self.resize(self.shot.width, self.shot.height)
        self.show_all()
        # 有些窗口管理器要等窗口 map 之后才认 resize/move，再来一次
        self.resize(self.shot.width, self.shot.height)
        self.move(x, y)
        self._grab_input()
        self._timeout_id = GLib.timeout_add(
            int(self.cfg.overlay_timeout_sec * 1000), self._on_timeout
        )
        self.present()

    def _grab_input(self) -> None:
        seat = Gdk.Display.get_default().get_default_seat()
        window = self.get_window()
        if window is not None:
            seat.grab(window, Gdk.SeatCapabilities.ALL, True, None, None, None)

    def _release_input(self) -> None:
        seat = Gdk.Display.get_default().get_default_seat()
        seat.ungrab()

    def _finish(self) -> None:
        """关闭浮层并**一定**通知 on_cancel —— 少通知一次，daemon 就会永远 busy。"""
        if self._done:
            return
        self._done = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        try:
            self._release_input()
        except Exception:
            pass
        self.destroy()
        self._on_cancel()

    def _on_destroy(self, _widget) -> None:
        # 关键：窗口被外部销毁（WM 关闭 / 出错）时也必须放开 grab ——
        # 面板用的是 Gdk SeatCapabilities.ALL（指针+键盘），漏放会让整个桌面收不到输入
        try:
            self._release_input()
        except Exception:
            pass
        # 同时兜底通知一次
        if not self._done:
            self._done = True
            self._on_cancel()

    def _on_timeout(self) -> bool:
        self._timeout_id = 0
        self._cancel()
        return False

    def _cancel(self) -> None:
        if self._done:
            return
        self._finish()

    # ---- 事件 --------------------------------------------------------
    def _on_press(self, _w, event) -> bool:
        if event.button != 1:
            self._cancel()
            return True
        x, y = int(event.x), int(event.y)
        self._start = (x, y)
        self._sel = (x, y, 0, 0)
        self.queue_draw()
        return True

    def _on_motion(self, _w, event) -> bool:
        if self._start is None:
            return False
        x, y = int(event.x), int(event.y)
        old = self._sel
        self._sel = _rect(self._start, (x, y))
        self._damage(old, self._sel)
        return True

    def _on_release(self, _w, event) -> bool:
        if self._start is None or event.button != 1:
            return True
        sel = _rect(self._start, (int(event.x), int(event.y)))
        self._start = None
        x, y, w, h = sel
        if w < self.cfg.min_crop_px or h < self.cfg.min_crop_px:
            self._cancel()
            return True
        self._done = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        try:
            self._release_input()
        except Exception:
            pass
        self.hide()
        self._on_selected(x, y, w, h)
        self.destroy()
        return True

    def _on_key(self, _w, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._cancel()
            return True
        return False

    def _damage(self, old, new) -> None:
        for rect in (old, new):
            if not rect:
                continue
            x, y, w, h = rect
            self.queue_draw_area(max(0, x - 3), max(0, y - 3), w + 6, h + 6)

    # ---- 绘制 --------------------------------------------------------
    def _on_draw(self, _w, cr) -> bool:
        Gdk.cairo_set_source_pixbuf(cr, self.shot.pixbuf, 0, 0)
        cr.paint()

        sel = self._sel
        if sel and sel[2] > 0 and sel[3] > 0:
            x, y, w, h = sel
            cr.set_source_rgba(0, 0, 0, self.cfg.dim)
            cr.rectangle(0, 0, self.shot.width, y)  # 上
            cr.rectangle(0, y + h, self.shot.width, self.shot.height - y - h)  # 下
            cr.rectangle(0, y, x, h)  # 左
            cr.rectangle(x + w, y, self.shot.width - x - w, h)  # 右
            cr.fill()

            cr.set_source_rgba(*_rgb(self.cfg.accent), 0.95)
            cr.set_line_width(1.0)
            cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
            cr.stroke()
            self._draw_label(cr, x, y, w, h)
        else:
            cr.set_source_rgba(0, 0, 0, self.cfg.dim * 0.6)
            cr.rectangle(0, 0, self.shot.width, self.shot.height)
            cr.fill()
            # 面板边框：一眼看清"可框选的范围到这里为止"
            cr.set_source_rgba(*_rgb(self.cfg.accent), 0.55)
            cr.set_line_width(1.0)
            cr.rectangle(0.5, 0.5, self.shot.width - 1, self.shot.height - 1)
            cr.stroke()
            if self.cfg.show_hint:
                self._draw_hint(cr)
        return True

    def _draw_label(self, cr, x: int, y: int, w: int, h: int) -> None:
        text = f"{w} × {h}"
        layout = PangoCairo.create_layout(cr)
        layout.set_text(text, -1)
        layout.set_font_description(Pango.FontDescription("Sans 10"))
        tw, th = layout.get_pixel_size()
        bx, by = x + 6, max(6, y - th - 12)
        cr.set_source_rgba(0.08, 0.08, 0.10, 0.82)
        cr.rectangle(bx - 5, by - 3, tw + 10, th + 6)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(bx, by)
        PangoCairo.show_layout(cr, layout)

    def _draw_hint(self, cr) -> None:
        text = "拖动框选  ·  Esc / 右键取消"
        layout = PangoCairo.create_layout(cr)
        layout.set_text(text, -1)
        layout.set_font_description(Pango.FontDescription("Sans 13"))
        tw, th = layout.get_pixel_size()
        bx = (self.shot.width - tw) / 2
        by = 48
        cr.set_source_rgba(0.08, 0.08, 0.10, 0.72)
        cr.rectangle(bx - 16, by - 10, tw + 32, th + 20)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.96)
        cr.move_to(bx, by)
        PangoCairo.show_layout(cr, layout)


def _rect(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int, int, int]:
    x0, y0 = a
    x1, y1 = b
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def _rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    if len(color) != 6:
        return (0.24, 0.68, 0.91)
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
