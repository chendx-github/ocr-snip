"""PyInstaller 打包入口（Linux）：静默启动托盘应用，默认 Qt 后端。

为什么 Linux 打包也用 Qt 而不是 GTK：GTK 后端依赖系统的 PyGObject + GTK3 库
（PyGObject 无法用 pip 安装），做"通用安装包"没法自带；PySide6 是 pip 包，
可以整包带走 —— 装了包就能跑，不需要用户在系统里补 gir1.2-gtk-3.0。
"""

from __future__ import annotations

import os
import sys
import traceback


def _ensure_streams() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        import os

        stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    except Exception:
        import io

        stream = io.StringIO()
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def main() -> int:
    _ensure_streams()
    # 本包只带 Qt（没有 PyGObject/GTK），让所有子命令都走 Qt 后端
    os.environ.setdefault("OCRSNIP_UI", "qt")
    try:
        from ocrsnip.cli import main as cli_main

        argv = sys.argv[1:]
        if not argv:
            argv = ["daemon", "--ui", "qt"]
        elif argv[0] == "daemon" and "--ui" not in argv:
            argv = [*argv, "--ui", "qt"]
        return cli_main(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception:  # pragma: no cover - 打包环境兜底
        try:
            from ocrsnip.config import log_path

            with open(log_path(), "a", encoding="utf-8") as handle:
                handle.write("启动失败:\n" + traceback.format_exc() + "\n")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
