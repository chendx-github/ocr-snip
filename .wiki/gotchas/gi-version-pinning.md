# 本机同时装 GTK3 和 GTK4：必须显式 require_version

日期：2026-11-19。

`from gi.repository import Gtk` 不指定版本时，一旦进程里先加载过 Gdk 4.0，后面再
`gi.require_version("Gdk","3.0")` 会直接抛：

```
ValueError: Namespace Gdk is already loaded with version 4.0
```

第一次踩到是在 `cli.py` 里为了"确保 GTK 初始化"随手写的一行 `from gi.repository import Gtk`，
它拿到了 GTK4，之后 daemon 就再也起不来。

## 约定

所有碰 gi 的模块，第一行必须是 `from . import gi_setup`（`src/ocrsnip/gi_setup.py`），
它统一固定 Gdk/Gtk/GdkPixbuf/Pango/PangoCairo 的版本。新增模块照着写。
