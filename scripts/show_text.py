#!/usr/bin/env python3
"""E2E 用：在固定位置显示一段文字（不依赖窗口管理器）。

用法: scripts/show_text.py "要显示的文字" [x] [y] [width] [height]
"""

import sys

from ocrsnip import gi_setup  # noqa: F401  (必须先于其它 gi 导入)
from gi.repository import Gdk, Gtk, Pango

text = sys.argv[1] if len(sys.argv) > 1 else "快捷截屏 识别测试 E2E-OCR-7788"
x = int(sys.argv[2]) if len(sys.argv) > 2 else 100
y = int(sys.argv[3]) if len(sys.argv) > 3 else 150
width = int(sys.argv[4]) if len(sys.argv) > 4 else 660
height = int(sys.argv[5]) if len(sys.argv) > 5 else 120

window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
window.set_decorated(False)
window.set_default_size(width, height)
window.move(x, y)

box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
box.set_border_width(18)
label = Gtk.Label()
label.set_xalign(0.0)
label.set_line_wrap(True)
label.modify_font(Pango.FontDescription("Noto Sans CJK SC 22"))
label.set_text(text)
box.pack_start(label, True, True, 0)

frame = Gtk.EventBox()
frame.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(1, 1, 1, 1))
frame.add(box)
window.add(frame)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
