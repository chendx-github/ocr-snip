"""把 OCR 出来的零散文本行拼成可直接粘贴的文本。

纯函数，无 GTK / 无 ONNX 依赖，便于单元测试。
"""

from __future__ import annotations

import re

_CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_CJK_END = re.compile(rf"[{_CJK}]$")
_CJK_START = re.compile(rf"^[{_CJK}]")
# 句末标点：出现在行尾说明这句话已经结束，不该和下一行拼在一起
_TERMINAL = tuple("。！？!?；;：:…")
# 行首就是列表/编号/标题符号时，换行必须保留
_BULLET_START = re.compile(r"^\s*(?:[•·*\-–—▪◦‣>|]|\(?\d{1,3}[.)、]|[（(]\d{1,3}[)）])")
_SPACES = re.compile(r"[ \t\u00a0]{2,}")
# 中文标点：和汉字一样，拼接时不该插入空格
_CJK_PUNCT = "，。、；：！？（）《》【】「」『』〈〉—…·～・"
_CJK_GAP = re.compile(rf"(?<=[{_CJK}])[ \t\u00a0]+(?=[{_CJK}])")


def clean_line(text: str) -> str:
    """行内清洗：去首尾空白、压缩连续空格。"""
    return _SPACES.sub(" ", text.replace("\u3000", " ")).strip()


def strip_cjk_spaces(text: str) -> str:
    """去掉中文之间被 OCR 插入的空格（'中 文' -> '中文'）。"""
    return _CJK_GAP.sub("", text)


def assemble(
    lines: list[str],
    mode: str = "smart",
    do_strip_cjk_spaces: bool = True,
    join_min_len: int = 20,
) -> str:
    """把 OCR 的文本行拼成结果文本。

    mode="lines"     保留每个识别行（代码、表格、菜单）
    mode="smart"     只把明显属于自动换行的行接回去（默认）
    mode="paragraph" 全部拼成一段
    """
    cleaned = [clean_line(line) for line in lines]
    cleaned = [line for line in cleaned if line]
    if not cleaned:
        return ""

    if mode == "lines":
        text = "\n".join(cleaned)
    elif mode == "paragraph":
        out: list[str] = []
        for line in cleaned:
            if out:
                out[-1] = _glue(out[-1], line)
            else:
                out.append(line)
        text = "".join(out)
    elif mode == "smart":
        out = []
        for line in cleaned:
            if out and _should_join(out[-1], line, join_min_len):
                out[-1] = _glue(out[-1], line)
            else:
                out.append(line)
        text = "\n".join(out)
    else:
        raise ValueError(f"unknown mode: {mode}")

    return strip_cjk_spaces(text) if do_strip_cjk_spaces else text


def _should_join(prev: str, cur: str, join_min_len: int) -> bool:
    if prev.endswith(_TERMINAL):
        return False
    if _BULLET_START.match(cur) or _BULLET_START.match(prev):
        return False
    last, first = prev[-1], cur[0]
    # 上一行以逗号/顿号结尾：句子还没完，接回去
    if last in "，,、":
        return True
    # 只有"写满一整行"的长行才认为是自动换行；短行更像菜单 / 代码 / 列表项
    if len(prev) < join_min_len:
        return False
    if _CJK_END.search(last) and (_CJK_START.match(first) or first.isalnum()):
        return True
    if last.isalnum() and (first.isalnum() or first in "(\"'"):
        return True
    return False


def _is_cjk(ch: str) -> bool:
    return bool(_CJK_END.search(ch)) or ch in _CJK_PUNCT


def _glue(prev: str, cur: str) -> str:
    last, first = prev[-1], cur[0]
    if _is_cjk(last) and _is_cjk(first):
        return prev + cur  # 中文（含中文标点）之间不加空格
    if last == "-" and first.islower():
        return prev[:-1] + cur  # 连字符断词
    return prev + " " + cur
