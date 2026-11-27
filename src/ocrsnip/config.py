"""Configuration: ~/.config/ocrsnip/config.toml with sane, speed-first defaults."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


def is_windows() -> bool:
    return sys.platform == "win32"


def config_dir() -> Path:
    if is_windows():
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "ocrsnip"
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "ocrsnip"


def config_path() -> Path:
    return config_dir() / "config.toml"


def data_dir() -> Path:
    """日志等本地数据（Windows 落 LOCALAPPDATA，不随漫游配置同步）。"""
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "ocrsnip"
    else:
        base = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")
        path = Path(base) / "ocrsnip"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "ocrsnip.log"


def last_png_path() -> Path:
    """每次选区都会存一份 PNG，方便"我要图不要字"的时候直接取。"""
    return data_dir() / "last.png"


def runtime_dir() -> Path:
    if is_windows():  # Qt 后端用 QLocalServer，不走这个目录
        return data_dir() / "run"
    base = os.environ.get("XDG_RUNTIME_DIR")
    path = Path(base) / "ocrsnip" if base else Path("/tmp") / f"ocrsnip-{os.getuid()}"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _display_slug() -> str:
    """按 DISPLAY 隔离 IPC 名字：同一个用户可以在多个 X 会话里各跑一个 daemon。"""
    display = os.environ.get("DISPLAY", "").strip() or "nodisplay"
    return re.sub(r"[^A-Za-z0-9]+", "_", display).strip("_")


def ipc_name() -> str:
    """Qt 后端（QLocalServer）用的实例名，客户端与服务端必须算得一样。"""
    import getpass

    try:
        user = getpass.getuser()
    except Exception:
        user = str(os.getuid()) if hasattr(os, "getuid") else "user"
    if is_windows():
        return f"ocrsnip-{user}"
    # Linux 上按 DISPLAY 隔离：测试实例/多会话之间不能互相抢单实例锁
    return f"ocrsnip-{user}-{_display_slug()}"


def socket_path() -> Path:
    return runtime_dir() / f"sock-{_display_slug()}"


def lock_path() -> Path:
    return socket_path().with_suffix(".lock")


@dataclass
class OcrConfig:
    # 区域截图里的字通常已经是"屏幕原生分辨率"，不需要让检测模型再把短边放大到 736。
    # limit_type=max 时只会缩小过大的选区，这是本项目最重要的一个性能开关。
    det_limit_type: str = "max"
    det_limit_side_len: int = 1024
    threads: int = 8
    rec_batch_num: int = 16
    use_cls: bool = False  # 角度分类器：截图基本是正向文本，关掉省 10-20ms
    min_score: float = 0.5
    # ORT 的 CPU arena 会缓存峰值显存式的堆；实测关掉更快也更省（见 mem.py）
    cpu_mem_arena: bool = False
    # 竖直方向补白，让紧贴边缘的文字不被裁断
    vertical_padding: bool = True


@dataclass
class PostConfig:
    # lines   : 保留原始换行（代码、菜单、表格）
    # smart   : 只把明显是"自动换行"的行接回去（默认）
    # paragraph: 全部拼成一段
    mode: str = "smart"
    strip_cjk_spaces: bool = True  # 去掉中文之间被 OCR 插进去的空格


@dataclass
class ClipboardConfig:
    also_primary: bool = False
    # true = 剪贴板放"选区图片(image/png)"而不是识别出的文字（X11 同一时刻只能持一种）
    copy_image: bool = False
    auto_paste: bool = False  # 复制后模拟 Ctrl+V，默认不做


@dataclass
class UiConfig:
    dim: float = 0.45
    accent: str = "#3daee9"
    overlay_timeout_sec: float = 45.0  # 兜底：忘记取消也不会卡住屏幕
    show_toast: bool = True
    toast_ms: int = 1100
    show_hint: bool = True
    min_crop_px: int = 4
    # 框选面板尺寸，优先级：fullscreen > panel_width/panel_height > panel_scale
    fullscreen: bool = False      # true = 面板占满鼠标所在显示器（整屏冻结画面）
    panel_width: int = 0          # 显式宽（像素）；0 = 按 panel_scale
    panel_height: int = 0         # 显式高（像素）；0 = 按 panel_scale
    # 边长 = 所在显示器对应边长 × panel_scale（0.5 => 1/2 宽 × 1/2 高 = 1/4 屏面积）
    panel_scale: float = 0.5
    panel_min_w: int = 360
    panel_min_h: int = 260


@dataclass
class Config:
    hotkey: str = "ctrl+alt+q"
    log_level: str = "info"
    ocr: OcrConfig = field(default_factory=OcrConfig)
    post: PostConfig = field(default_factory=PostConfig)
    clipboard: ClipboardConfig = field(default_factory=ClipboardConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        cfg = cls(path=path)
        if not path.exists():
            return cfg
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            cfg.warnings.append(f"{path}: {exc}")
            return cfg
        _merge(cfg, raw, "", cfg.warnings)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.post.mode not in ("lines", "smart", "paragraph"):
            self.warnings.append(f"post.mode={self.post.mode!r} 无效，回退为 smart")
            self.post.mode = "smart"
        self.ocr.threads = max(1, min(32, self.ocr.threads))
        self.ocr.rec_batch_num = max(1, min(64, self.ocr.rec_batch_num))
        self.ocr.det_limit_side_len = max(320, min(4096, self.ocr.det_limit_side_len))
        self.ui.dim = max(0.0, min(0.9, self.ui.dim))
        self.ui.panel_scale = max(0.15, min(1.0, self.ui.panel_scale))
        self.ui.panel_width = max(0, min(16384, self.ui.panel_width))
        self.ui.panel_height = max(0, min(16384, self.ui.panel_height))


def _merge(obj: Any, raw: dict[str, Any], prefix: str, warnings: list[str]) -> None:
    known = {f.name: f for f in fields(obj)}
    for key, value in raw.items():
        name = key.replace("-", "_")
        f = known.get(name)
        if f is None:
            warnings.append(f"未知配置项 {prefix}{key}（已忽略）")
            continue
        current = getattr(obj, name)
        if is_dataclass(current):
            if isinstance(value, dict):
                _merge(current, value, f"{prefix}{key}.", warnings)
            else:
                warnings.append(f"{prefix}{key} 应为表（已忽略）")
            continue
        if isinstance(current, bool) and not isinstance(value, bool):
            warnings.append(f"{prefix}{key} 应为布尔值（已忽略）")
            continue
        setattr(obj, name, value)


DEFAULT_CONFIG_TOML = """\
# ocrsnip 配置 —— 全部项都可省略，下面是默认值
hotkey = "ctrl+alt+q"          # 也支持 super+shift+s / print 等；改后需重启 daemon
log_level = "info"

[ocr]
det_limit_type = "max"         # 不要改成 min，否则小选区会被放大，延迟翻数倍
det_limit_side_len = 1024      # 选区最长边超过它才缩小
threads = 8
rec_batch_num = 16
use_cls = false
min_score = 0.5
cpu_mem_arena = false          # 关掉 ORT arena：更省内存，实测还更快

[post]
mode = "smart"                 # lines | smart | paragraph
strip_cjk_spaces = true

[clipboard]
also_primary = false
copy_image = false             # true 则放图片而不是文字
auto_paste = false             # true 则复制后自动 Ctrl+V

[ui]
fullscreen = false             # true = 面板占满鼠标所在显示器（整屏冻结画面）
panel_width = 0                # 显式面板宽（像素）；0 = 按 panel_scale
panel_height = 0               # 显式面板高（像素）；0 = 按 panel_scale
panel_scale = 0.5              # 面板占所在显示器的边长比例；0.5 = 1/4 屏面积
dim = 0.45
accent = "#3daee9"
overlay_timeout_sec = 45.0
show_toast = true
toast_ms = 1100
show_hint = true
"""
