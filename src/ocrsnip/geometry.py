"""面板矩形的纯计算（无 GTK 依赖，便于单元测试）。"""

from __future__ import annotations


def panel_rect(
    pointer: tuple[int, int],
    monitor: tuple[int, int, int, int],
    scale: float = 0.5,
    min_size: tuple[int, int] = (360, 260),
    fullscreen: bool = False,
    size: tuple[int, int] = (0, 0),
) -> tuple[int, int, int, int]:
    """以鼠标为中心的面板，夹在单个显示器范围内，返回屏幕坐标 (x, y, w, h)。

    尺寸优先级：fullscreen > size（显式宽/高，0 表示该项按比例） > scale。
    scale=0.5 时是 1/2 宽 × 1/2 高 = 1/4 屏面积；fullscreen 时面板就是整个显示器。
    """
    mx, my, mw, mh = monitor
    if fullscreen:
        return mx, my, mw, mh
    px, py = pointer
    scale = max(0.15, min(1.0, scale))
    want_w, want_h = (int(size[0]), int(size[1])) if size else (0, 0)

    # 显式尺寸优先（用户说了算，不受 min_size 影响，只夹到显示器范围）
    if want_w > 0:
        width = min(want_w, mw)
    else:
        width = max(min(mw, min_size[0]), min(int(round(mw * scale)), mw))
    if want_h > 0:
        height = min(want_h, mh)
    else:
        height = max(min(mh, min_size[1]), min(int(round(mh * scale)), mh))

    x = px - width // 2
    y = py - height // 2
    x = max(mx, min(x, mx + mw - width))
    y = max(my, min(y, my + mh - height))
    return x, y, width, height


def panel_physical(
    panel: tuple[int, int, int, int],
    origin: tuple[int, int],
    dpr: float,
) -> tuple[int, int, int, int]:
    """逻辑坐标 → 某块截图里的物理像素矩形。

    Qt 在 Windows 上给的是逻辑坐标（受显示缩放影响），而抓到的 pixmap 是物理像素，
    换算必须乘 devicePixelRatio，并且减掉该屏截图的逻辑原点。
    """
    x, y, w, h = panel
    return (
        round((x - origin[0]) * dpr),
        round((y - origin[1]) * dpr),
        max(1, round(w * dpr)),
        max(1, round(h * dpr)),
    )
