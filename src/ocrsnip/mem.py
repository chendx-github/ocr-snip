"""内存相关的收尾动作。

为什么需要：ONNX Runtime 的 CPU arena + glibc 的 malloc arena 都会"记住"峰值，
长时间常驻的托盘程序会看起来很胖（实测一次跑到 900MB）。策略是
**关掉 ORT arena**（本机实测还更快），并在每次识别后把 glibc 的空闲页还给系统。
"""

from __future__ import annotations

import ctypes
import logging
import os

log = logging.getLogger("ocrsnip")

_trim = None
if hasattr(ctypes, "CDLL"):
    try:
        _libc = ctypes.CDLL("libc.so.6")
        _trim = _libc.malloc_trim
        _trim.argtypes = [ctypes.c_size_t]
        _trim.restype = ctypes.c_int
    except OSError:  # macOS / musl / Windows
        _trim = None


def rss_mb(pid: int | None = None) -> float | None:
    pid = pid or os.getpid()
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def trim() -> None:
    """把 glibc 里空闲的堆页还给系统（非 glibc 平台上是空操作）。"""
    if _trim is not None:
        try:
            _trim(0)
        except Exception:
            pass


class MemoryProbe:
    """每 N 次动作记一条 RSS 日志，方便发现回归。"""

    def __init__(self, every: int = 20) -> None:
        self.every = max(1, every)
        self.count = 0

    def tick(self, action: str) -> None:
        self.count += 1
        trim()
        if self.count % self.every == 0:
            value = rss_mb()
            if value is not None:
                log.info("%s 累计 %d 次，RSS %.0f MB", action, self.count, value)
