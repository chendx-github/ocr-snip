"""Windows 剪贴板：一次放入多格式（文本 + PNG + CF_DIB）。

X11 那边我们自己是 selection owner、一次 advertise 多个 target；
Windows 天然支持"一个剪贴板内容多种格式"，所以粘到编辑器出文字、粘到聊天出图。

为什么还要 CF_DIB：很多老程序（画图、部分 Office 版本）只认 CF_DIB 不认 PNG。
"""

from __future__ import annotations

import ctypes
import logging
import struct
from ctypes import wintypes

log = logging.getLogger("ocrsnip.win_clipboard")

CF_UNICODETEXT = 13
CF_DIB = 8
GMEM_MOVEABLE = 0x0002

_user32 = ctypes.WinDLL("user32", use_last_error=True) if hasattr(ctypes, "WinDLL") else None
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if _user32 else None

if _user32 is not None:  # 64 位下必须声明返回类型，否则句柄被截断成 32 位
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.GetClipboardData.restype = wintypes.HANDLE
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.RegisterClipboardFormatW.restype = wintypes.UINT
    _user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]


def dib_from_bgra(bgra, width: int, height: int) -> bytes:
    """把 BGRA（top-down，含 stride）转成 CF_DIB 需要的字节流。

    CF_DIB = BITMAPINFOHEADER(40B) + 像素；biHeight 为正表示**自底向上**，
    所以这里要把行顺序翻转，并把每像素 4 字节原样保留（32bpp BI_RGB）。
    """
    import numpy as np

    array = np.asarray(bgra, dtype=np.uint8)
    if array.ndim == 3:
        if array.shape[2] == 4:
            pixels = array
        else:  # 只有 BGR：补 alpha
            alpha = np.full(array.shape[:2] + (1,), 255, dtype=np.uint8)
            pixels = np.concatenate([array, alpha], axis=2)
    else:  # 扁平数组 + stride
        pixels = array.reshape(height, -1)[:, : width * 4].reshape(height, width, 4)

    flipped = np.ascontiguousarray(pixels[::-1])  # bottom-up
    header = struct.pack(
        "<IiiHHIIiiII",
        40,            # biSize
        width,         # biWidth
        height,        # biHeight（正 = bottom-up）
        1,             # biPlanes
        32,            # biBitCount
        0,             # biCompression = BI_RGB
        width * height * 4,
        0,
        0,
        0,
        0,
    )
    return header + flipped.tobytes()


def _global_ptr(data: bytes):
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise OSError("GlobalAlloc 失败")
    pointer = _kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    _kernel32.GlobalUnlock(handle)
    return handle


def copy(text: str | None = None, png: bytes | None = None, dib: bytes | None = None) -> str:
    """一次性把多种格式放进剪贴板，返回实际放了哪些格式。"""
    if _user32 is None:
        return "none"
    formats: list[str] = []
    if not _user32.OpenClipboard(None):
        log.warning("OpenClipboard 失败（错误码 %s）", ctypes.get_last_error())
        return "none"
    try:
        _user32.EmptyClipboard()
        if text is not None:
            payload = text.encode("utf-16-le") + b"\x00\x00"
            _user32.SetClipboardData(CF_UNICODETEXT, _global_ptr(payload))
            formats.append("text")
        if dib is not None:
            _user32.SetClipboardData(CF_DIB, _global_ptr(dib))
            formats.append("dib")
        if png is not None:
            fmt = _user32.RegisterClipboardFormatW("PNG")
            if fmt:
                _user32.SetClipboardData(fmt, _global_ptr(png))
                formats.append("png")
    finally:
        _user32.CloseClipboard()
    return "+".join(formats) or "none"


def copy_image(png: bytes, dib: bytes | None = None) -> str:
    return copy(png=png, dib=dib)


def available() -> bool:
    return _user32 is not None
