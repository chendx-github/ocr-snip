"""轻量提示条：不抢焦点，几秒后自己消失。"""

from __future__ import annotations

from . import gi_setup  # noqa: F401  (必须先于其它 gi 导入)
from gi.repository import Gdk, GLib, Gtk


class Toast(Gtk.Window):
    def __init__(self, text: str, duration_ms: int = 1100, error: bool = False) -> None:
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_border_width(10)
        label = Gtk.Label()
        label.set_markup(
            f'<span foreground="{"#ff8a80" if error else "#ffffff"}">{_escape(text)}</span>'
        )
        box.pack_start(label, False, False, 0)

        frame = Gtk.EventBox()
        frame.add(box)
        frame.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(*(0.75, 0.18, 0.18, 0.94) if error else (0.11, 0.11, 0.13, 0.94)),
        )
        self.add(frame)
        self._duration_ms = max(200, duration_ms)

    def show_briefly(self, x: int | None = None, y: int | None = None) -> None:
        self.show_all()
        width, height = self.get_size()
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geo = monitor.get_geometry()
        if x is None or y is None:
            x = geo.x + (geo.width - width) // 2
            y = geo.y + geo.height - height - 80
        self.move(x, y)
        GLib.timeout_add(self._duration_ms, self._close)

    def _close(self) -> bool:
        self.destroy()
        return False


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", " ")
    )
