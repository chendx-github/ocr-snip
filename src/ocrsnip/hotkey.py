"""X11 全局热键（XGrabKey），不依赖 xbindkeys / 桌面环境配置。

注意：X11 的键盘抓取是"独占"的，同一个组合键只能被一个客户端抓取；
冲突时会抛 HotkeyUnavailable，ocrsnip doctor 会把它显示出来。
"""

from __future__ import annotations

import threading

from Xlib import X, XK, display as xdisplay
from Xlib.error import BadAccess, DisplayError

_ALIASES = {
    "print": "Print",
    "printscreen": "Print",
    "prtsc": "Print",
    "enter": "Return",
    "return": "Return",
    "esc": "Escape",
    "escape": "Escape",
    "space": "space",
    "tab": "Tab",
    "backspace": "BackSpace",
    "delete": "Delete",
    "del": "Delete",
    "insert": "Insert",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}

_MOD_NAMES = {
    "ctrl": X.ControlMask,
    "control": X.ControlMask,
    "alt": X.Mod1Mask,
    "mod1": X.Mod1Mask,
    "shift": X.ShiftMask,
    "super": X.Mod4Mask,
    "win": X.Mod4Mask,
    "meta": X.Mod4Mask,
    "mod4": X.Mod4Mask,
}


class HotkeyUnavailable(RuntimeError):
    pass


def parse_hotkey(spec: str) -> tuple[int, str]:
    """'ctrl+alt+q' -> (修饰键掩码, 键名)。"""
    tokens = [t.strip() for t in spec.split("+") if t.strip()]
    if not tokens:
        raise ValueError("空的热键配置")
    key = tokens[-1]
    mask = 0
    for token in tokens[:-1]:
        low = token.lower()
        if low in _MOD_NAMES:
            mask |= _MOD_NAMES[low]
        elif low.startswith("mod") and low[3:].isdigit():
            mask |= getattr(X, f"Mod{int(low[3:])}Mask")
        else:
            raise ValueError(f"无法识别的修饰键: {token}")
    return mask, key


def _keysym(key: str) -> int:
    name = _ALIASES.get(key.lower(), key)
    candidates = [name, name.capitalize(), name.upper()]
    for candidate in candidates:
        sym = XK.string_to_keysym(candidate)
        if sym:
            return sym
    raise ValueError(f"无法识别的键名: {key}")


class HotkeyListener:
    def __init__(self, spec: str, callback) -> None:
        self.spec = spec
        self._callback = callback
        self._display = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._keycode = 0
        self._mask = 0
        self._ignored_masks: list[int] = []

    def start(self) -> None:
        try:
            self._display = xdisplay.Display()
        except DisplayError as exc:  # pragma: no cover - 环境相关
            raise HotkeyUnavailable(f"无法连接 X11: {exc}") from exc

        mask, key = parse_hotkey(self.spec)
        keycode = self._display.keysym_to_keycode(_keysym(key))
        if not keycode:
            raise HotkeyUnavailable(f"当前键盘布局里没有这个键: {key}")

        self._mask = mask
        self._keycode = keycode
        root = self._display.screen().root
        errors: list[str] = []

        def handler(err, _request):  # noqa: ANN001
            errors.append(str(err))
            return 0

        self._display.set_error_handler(handler)
        lock_mask = X.LockMask
        num_mask = X.Mod2Mask
        for extra in (0, lock_mask, num_mask, lock_mask | num_mask):
            self._ignored_masks.append(extra)
            root.grab_key(
                keycode,
                mask | extra,
                True,
                X.GrabModeAsync,
                X.GrabModeAsync,
            )
        self._display.sync()
        if errors:
            raise HotkeyUnavailable(
                f"热键 {self.spec} 抓取失败（可能已被其它程序占用）: {errors[0]}"
            )

        root.change_attributes(event_mask=X.KeyPressMask)
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ocrsnip-hotkey", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running and self._display is not None:
            try:
                event = self._display.next_event()
            except Exception:  # pragma: no cover - 关闭时的竞态
                return
            if getattr(event, "type", None) != X.KeyPress:
                continue
            if event.detail != self._keycode:
                continue
            state = event.state & ~(X.LockMask | X.Mod2Mask)
            if state != self._mask:
                continue
            try:
                self._callback()
            except Exception:
                pass

    def stop(self) -> None:
        self._running = False
        if self._display is None:
            return
        try:
            root = self._display.screen().root
            for extra in self._ignored_masks:
                root.ungrab_key(self._keycode, self._mask | extra)
            self._display.sync()
        except Exception:
            pass
        try:
            self._display.close()
        except Exception:
            pass
        self._display = None


def probe(spec: str) -> str:
    """doctor 用：尝试抓取一次并立即释放，返回人可读结论。"""
    listener = HotkeyListener(spec, lambda: None)
    try:
        listener.start()
    except HotkeyUnavailable as exc:
        return f"不可用：{exc}"
    except (ValueError, BadAccess) as exc:
        return f"不可用：{exc}"
    finally:
        try:
            listener.stop()
        except Exception:
            pass
    return "可用"
