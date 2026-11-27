"""PyInstaller / 打包入口：静默启动托盘应用。

PyInstaller 的 windowed 模式里 sys.stdout/stderr 是 None，直接 print() 会炸，
所以先给它们一个兜底目标。

注意：**不要**把它们指到日志文件 —— logging 的 FileHandler 已经在写同一个文件，
再叠加一个 StreamHandler(stderr) 就会让每行日志重复两遍。这里丢给 devnull 即可；
真正的错误由 main() 的 except 分支直接写日志。
"""

from __future__ import annotations

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
    try:
        from ocrsnip.cli import main as cli_main

        argv = sys.argv[1:] or ["daemon", "--ui", "qt"]
        return cli_main(argv)
    except SystemExit as exc:  # argparse / --help
        return int(exc.code or 0)
    except Exception:  # pragma: no cover - 打包环境下兜底，别静默崩溃
        try:
            from ocrsnip.config import log_path

            with open(log_path(), "a", encoding="utf-8") as handle:
                handle.write("启动失败:\n" + traceback.format_exc() + "\n")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
