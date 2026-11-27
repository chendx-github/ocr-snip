"""Windows 全局热键（user32!RegisterHotKey）。

Windows 的 RegisterHotKey 必须由"会一直 pump 消息"的线程调用，所以这里单独开一个线程：
注册 → GetMessageW 循环 → 收到 WM_HOTKEY 就回调 → 退出时 PostThreadMessage(WM_QUIT)。
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "super": MOD_WIN,
    "win": MOD_WIN,
    "meta": MOD_WIN,
}

# 非字母数字键的虚拟键码
_VK = {
    "print": 0x2C,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "snapshot": 0x2C,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "`": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
    "\\": 0xDC,
    "pause": 0x13,
    "capslock": 0x14,
}


class HotkeyError(RuntimeError):
    pass


def parse_hotkey_win(spec: str) -> tuple[int, int]:
    """'ctrl+alt+q' → (修饰键, 虚拟键码)。纯函数，便于在 Linux 上单测。"""
    tokens = [token.strip() for token in spec.split("+") if token.strip()]
    if not tokens:
        raise ValueError("空的热键配置")
    key = tokens[-1]
    mods = MOD_NOREPEAT
    for token in tokens[:-1]:
        low = token.lower()
        if low in _MODS:
            mods |= _MODS[low]
        else:
            raise ValueError(f"无法识别的修饰键: {token}")
    return mods, key_to_vk(key)


def key_to_vk(key: str) -> int:
    low = key.lower()
    if low in _VK:
        return _VK[low]
    if len(key) == 1 and (key.isalnum() or key in "`-=[];',./\\"):
        return ord(key.upper())
    if low.startswith("f") and low[1:].isdigit():
        number = int(low[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1
    raise ValueError(f"无法识别的键名: {key}")


class WinHotkey(threading.Thread):
    """后台线程：注册热键并 pump 消息。"""

    def __init__(self, spec: str, callback) -> None:
        super().__init__(name="ocrsnip-hotkey", daemon=True)
        self.spec = spec
        self._callback = callback
        self._mods, self._vk = parse_hotkey_win(spec)
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None

    def start(self) -> None:
        super().start()
        self._ready.wait(5.0)
        if self._error:
            raise HotkeyError(self._error)

    def run(self) -> None:
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
        except (AttributeError, OSError) as exc:  # 非 Windows 上被误用
            self._error = f"无法加载 user32: {exc}"
            self._ready.set()
            return

        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, self._mods, self._vk):
            code = ctypes.get_last_error()
            self._error = (
                f"热键 {self.spec} 注册失败（错误码 {code}）：可能已被其它程序占用"
            )
            self._ready.set()
            return

        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == 1:
                    try:
                        self._callback()
                    except Exception:
                        pass
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


def available() -> bool:
    return hasattr(ctypes, "WinDLL")
