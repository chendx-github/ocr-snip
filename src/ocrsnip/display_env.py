"""确定 DISPLAY：开机/登录自启时，DISPLAY 往往还没进 systemd 用户环境。"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger("ocrsnip")

_SOCKET_DIR = Path("/tmp/.X11-unix")


def _connectable(display: str) -> bool:
    try:
        from Xlib import display as xdisplay

        conn = xdisplay.Display(display)
        conn.close()
        return True
    except Exception:
        return False


def candidates() -> list[str]:
    """候选 display，本地 :0 优先，其余按编号排序。"""
    found: list[str] = []
    try:
        for entry in sorted(_SOCKET_DIR.iterdir()):
            name = entry.name
            if name.startswith("X") and name[1:].isdigit():
                found.append(f":{name[1:]}")
    except OSError:
        pass
    found.sort(key=lambda value: (value != ":0", int(value[1:])))
    return found


def ensure_display(timeout: float = 20.0) -> str | None:
    """返回可用的 DISPLAY；必要时写入环境变量。

    开机自启时 X 可能还没就绪，所以会重试到 timeout 秒。
    """
    current = os.environ.get("DISPLAY")
    if current and _connectable(current):
        return current

    deadline = time.monotonic() + timeout
    tried: list[str] = []
    while True:
        for candidate in candidates():
            if candidate in tried and time.monotonic() + 3 > deadline:
                continue
            if _connectable(candidate):
                os.environ["DISPLAY"] = candidate
                if current != candidate:
                    log.warning("DISPLAY 未设置/不可用（%s），自动使用 %s", current, candidate)
                return candidate
            if candidate not in tried:
                tried.append(candidate)
        if time.monotonic() >= deadline:
            log.error("找不到可用的 X11 display（候选：%s）", candidates() or "无")
            return None
        time.sleep(0.5)
