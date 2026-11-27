"""X11 剪贴板多 target 服务（从 x11rect 内联，只保留剪贴板部分）。

为什么保留：X11 上一个 owner 可以同时应答 UTF8_STRING/STRING/text-plain/image-png，
比"先 xclip 文本再 xclip -t image/png"稳（后者会把前一次的 owner 顶掉）。

用独立进程持有剪贴板（python -m ocrsnip.x11_clip）：本项目是多线程，
fork 出来的子进程容易死锁，所以走 subprocess。
"""

from __future__ import annotations

import argparse
import logging
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time


log = logging.getLogger("ocrsnip.x11_clip")

MIN_SIDE = 3

def require_x11(display_name: str | None = None):
    """懒加载 python-xlib；非 X11 平台给出人话报错，而不是让 import 时炸在第三方包里。"""
    if sys.platform not in ("linux", "linux2", "freebsd", "openbsd", "netbsd"):
        raise RuntimeError(
            f"X11 剪贴板只能在 X11 桌面使用（当前平台 {sys.platform}）。"
            "Wayland 请用 xdg-desktop-portal。"
        )
    try:
        from Xlib import XK, X, Xatom, Xcursorfont, display
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 python-xlib：pip install python-xlib") from exc
    if display_name is None and not __import__("os").environ.get("DISPLAY"):
        raise RuntimeError("没有 DISPLAY 环境变量，无法连接 X11")
    return X, XK, Xcursorfont, Xatom, display

_TEXT_TARGETS = ("UTF8_STRING", "text/plain;charset=utf-8", "text/plain", "STRING")


def _server_timestamp(conn, window, X, Xatom) -> int:
    """改一次属性并等 PropertyNotify，拿到服务器当前时间（比 X.CurrentTime 安全）。"""
    prop = conn.intern_atom("_OCRSNIP_STAMP")
    # 必须先订阅 PropertyChangeMask，否则收不到 PropertyNotify
    window.change_attributes(event_mask=X.PropertyChangeMask)
    window.change_property(prop, Xatom.STRING, 8, b"x", X.PropModeAppend)
    conn.sync()
    for _ in range(50):
        select.select([conn], [], [], 0.1)
        while conn.pending_events():
            event = conn.next_event()
            if getattr(event, "type", None) == X.PropertyNotify and getattr(event, "window", None) == window:
                return int(event.time)
    log.warning("拿不到服务器时间戳，退回 CurrentTime")
    return 0  # X.CurrentTime


def _write_bytes(window, prop, prop_type, data: bytes, X) -> None:
    """8 位数据（文本/PNG）。"""
    window.change_property(prop, prop_type, 8, data, X.PropModeReplace)


def _write_atoms(window, prop, prop_type, values, X) -> None:
    """32 位数据（TARGETS / TIMESTAMP 必须是 format=32，否则客户端读不对）。"""
    window.change_property(prop, prop_type, 32, list(values), X.PropModeReplace)


def serve(
    text: str | None = None,
    png: bytes | None = None,
    timeout: float | None = None,
    display_name: str | None = None,
) -> str:
    """在当前进程里持有 CLIPBOARD 直到被别的客户端抢走（或超时）。

    返回结束原因："selection-clear"（被别人抢走，正常结束）
              / "timeout"（调试用，默认无限）
              / "no-targets"（text 和 png 都空）
              / "no-owner"（没能取得 CLIPBOARD ownership）
    """
    if not text and not png:
        return "no-targets"

    X, _XK, _Font, Xatom, display = require_x11(display_name)
    conn = display.Display(display_name)
    screen = conn.screen()
    root = screen.root
    # 一个不可见的小窗口当 owner
    window = root.create_window(0, 0, 1, 1, 0, X.CopyFromParent, X.InputOutput, X.CopyFromParent)
    atoms = {name: conn.intern_atom(name) for name in ("CLIPBOARD", "TARGETS", "TIMESTAMP", *_TEXT_TARGETS, "image/png")}
    conn.set_error_handler(lambda err, req: 0)  # 请求方窗口可能已销毁：忽略，别崩

    # 时间戳竞态：不能用 X.CurrentTime（两个客户端都用 CurrentTime 时"后到者赢"，
    # 会把别人刚放好的剪贴板抢掉）。标准做法：改一次属性，等 PropertyNotify 拿到真实时间。
    stamp = _server_timestamp(conn, window, X, Xatom)
    window.set_selection_owner(atoms["CLIPBOARD"], stamp)
    conn.sync()
    if conn.get_selection_owner(atoms["CLIPBOARD"]) != window:  # getter 在 display 上
        log.warning("没能取得 CLIPBOARD ownership")
        conn.close()
        return "no-owner"

    # STRING 的语义是 Latin-1，只认它的老客户端（Tk/部分 Java）会把中文粘成乱码，
    # 所以只有纯 ASCII 文本才 advertise STRING。
    text_targets = [name for name in _TEXT_TARGETS if name != "STRING"] + (
        ["STRING"] if text and text.isascii() else []
    )
    targets = [atoms["TARGETS"], atoms["TIMESTAMP"]]
    if text:
        targets += [atoms[name] for name in text_targets]
    if png:
        targets.append(atoms["image/png"])

    text_bytes = text.encode("utf-8") if text else None
    deadline = None if timeout is None else time.monotonic() + timeout

    try:
        while True:
            if deadline is not None and time.monotonic() > deadline:
                return "timeout"
            while conn.pending_events():
                event = conn.next_event()
                if event.type == X.SelectionClear:
                    return "selection-clear"
                if event.type != X.SelectionRequest:
                    continue
                request = event
                prop = request.property if request.property != X.NONE else request.target
                payload: bytes | list[int] | None = None
                payload_type = request.target
                if request.target == atoms["TARGETS"]:
                    payload = [int(atom) for atom in targets]
                    payload_type = Xatom.ATOM
                elif request.target == atoms["TIMESTAMP"]:
                    payload = [int(request.time)]
                    payload_type = Xatom.INTEGER
                elif text_bytes is not None and any(
                    request.target == atoms[name] for name in text_targets
                ):
                    payload = text_bytes
                    payload_type = (
                        atoms["STRING"]
                        if request.target == atoms["STRING"]
                        else atoms["UTF8_STRING"]
                    )
                elif png is not None and request.target == atoms["image/png"]:
                    if len(png) > 256 * 1024:
                        # 超过 X 单次请求上限（BIG-REQUESTS≈16MB）时 change_property 会
                        # BadLength，我们装了 error handler 会静默 —— 至少留一条日志。
                        log.warning(
                            "PNG 较大（%d KB），可能超出 X 单请求上限；如客户端拿到空图请改为存文件",
                            len(png) // 1024,
                        )
                    payload = png
                    payload_type = atoms["image/png"]

                try:
                    if payload is None:
                        notify_prop = X.NONE  # 拒绝：property=NONE
                    elif isinstance(payload, list):
                        _write_atoms(request.requestor, prop, payload_type, payload, X)
                        notify_prop = prop
                    else:
                        _write_bytes(request.requestor, prop, payload_type, payload, X)
                        notify_prop = prop
                    from Xlib.protocol import event as xevent

                    notify = xevent.SelectionNotify(
                        time=request.time,
                        requestor=request.requestor,
                        selection=request.selection,
                        target=request.target,
                        property=notify_prop,
                    )
                    request.requestor.send_event(notify)
                    conn.flush()
                except Exception as exc:  # 请求窗口可能已经消失
                    log.debug("应答 SelectionRequest 失败: %s", exc)
            select.select([conn], [], [], 0.2)
    finally:
        try:
            window.destroy()
        except Exception:
            pass
        conn.close()


def spawn(
    text: str | None = None,
    png: bytes | None = None,
    timeout: float = 0,  # 0 / 负数 = 只等 SelectionClear（推荐）；>0 仅供调试
) -> bool:
    """起一个独立进程持有剪贴板，立刻返回。

    用独立进程而不是 fork：本项目是多线程（GTK/OCR 线程），fork 后子进程容易死锁。
    """
    if not text and not png:
        return False
    handle = tempfile.mkdtemp(prefix="ocrsnip-clip-")
    text_path = os.path.join(handle, "text.txt")
    png_path = os.path.join(handle, "img.png")
    argv = [sys.executable, "-m", "ocrsnip.x11_clip", "--dir", handle, "--timeout", str(max(0.0, timeout))]
    try:
        if text:
            with open(text_path, "w", encoding="utf-8") as fh:
                fh.write(text)
        if png:
            with open(png_path, "wb") as fh:
                fh.write(png)
    except OSError as exc:
        log.warning("写临时文件失败: %s", exc)
        shutil.rmtree(handle, ignore_errors=True)
        return False

    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # 与父进程解耦，父进程退出后仍可服务剪贴板
        )
        return True
    except OSError as exc:
        log.warning("启动剪贴板进程失败: %s", exc)
        shutil.rmtree(handle, ignore_errors=True)
        return False


def copy_text(text: str) -> bool:
    """只要文本时最省事的路径：xclip 优先，退回自己当 owner。"""
    exe = shutil.which("xclip")
    if exe:
        try:
            subprocess.run([exe, "-selection", "clipboard", "-i"], input=text.encode("utf-8"), check=True, timeout=3)
            return True
        except (subprocess.SubprocessError, OSError):
            pass
    return spawn(text=text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ocrsnip.x11_clip", description="持有剪贴板并按 target 应答")
    parser.add_argument("--dir", required=True, help="含 text.txt / img.png 的目录")
    parser.add_argument(
        "--timeout", type=float, default=0,
        help="调试用：N 秒后自动退出。默认 0 = 一直持有到被别人抢走",
    )
    args = parser.parse_args(argv)

    text = png = None
    text_path = os.path.join(args.dir, "text.txt")
    png_path = os.path.join(args.dir, "img.png")
    try:
        if os.path.exists(text_path):
            with open(text_path, encoding="utf-8") as fh:
                text = fh.read()
        if os.path.exists(png_path):
            with open(png_path, "rb") as fh:
                png = fh.read()
    except OSError:
        pass
    finally:
        shutil.rmtree(args.dir, ignore_errors=True)

    reason = serve(text=text, png=png, timeout=args.timeout if args.timeout > 0 else None)
    log.debug("剪贴板服务结束：%s", reason)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
