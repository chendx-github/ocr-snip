"""剪贴板写入：优先 xclip（fork 后继续托管选区，本进程退出内容也不会丢）。"""

from __future__ import annotations

import shutil
import subprocess


def _xclip(text: str, selection: str) -> bool:
    exe = shutil.which("xclip")
    if not exe:
        return False
    try:
        subprocess.run(
            [exe, "-selection", selection, "-i"],
            input=text.encode("utf-8"),
            check=True,
            timeout=3,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def _gtk(text: str, selection: str) -> bool:
    try:
        from . import gi_setup  # noqa: F401
        from gi.repository import Gdk, Gtk

        clipboard = Gtk.Clipboard.get(
            Gdk.SELECTION_CLIPBOARD if selection == "clipboard" else Gdk.SELECTION_PRIMARY
        )
        clipboard.set_text(text, -1)
        clipboard.store()
        return True
    except Exception:
        return False


def copy(text: str, also_primary: bool = False) -> str:
    """把文本放进剪贴板，返回实际使用的后端名。"""
    backend = "xclip" if _xclip(text, "clipboard") else ("gtk" if _gtk(text, "clipboard") else "none")
    if also_primary:
        if not _xclip(text, "primary"):
            _gtk(text, "primary")
    return backend


def copy_image(image) -> str:
    """把 PIL.Image 以 image/png 放进剪贴板（xclip 会 fork 常驻）。

    注意：X11 的剪贴板同一时刻只能由一个客户端持有，所以"图片"和"文本"
    不能同时都在剪贴板上 —— 由配置项 clipboard.copy_image 二选一。
    """
    import tempfile

    exe = shutil.which("xclip")
    if exe is None or image is None:
        return "none"
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    path = handle.name
    handle.close()
    try:
        image.save(path, format="PNG")
        subprocess.Popen(
            [exe, "-selection", "clipboard", "-t", "image/png", "-i", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "xclip-image"
    except Exception:
        return "none"
    finally:
        # xclip 会 fork 并自己读文件，稍后再删
        import threading

        threading.Timer(3.0, lambda: _silent_unlink(path)).start()


def _silent_unlink(path: str) -> None:
    try:
        import os

        os.unlink(path)
    except OSError:
        pass


def paste() -> None:
    """模拟一次 Ctrl+V（用于 auto_paste）。"""
    exe = shutil.which("xdotool")
    if not exe:
        return
    subprocess.run(
        [exe, "key", "--clearmodifiers", "ctrl+v"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=3,
    )
