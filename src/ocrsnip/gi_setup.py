"""统一在第一次碰 gi 之前固定版本：本机同时装了 GTK3 和 GTK4，
不显式 require_version 的话默认会拿到 4.0，和我们的窗口代码不兼容。
"""

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
