from ocrsnip.postprocess import assemble, clean_line, strip_cjk_spaces


def test_clean_line_trims_and_squashes_spaces():
    assert clean_line("  Ctrl   +   Q  ") == "Ctrl + Q"
    assert clean_line("全角\u3000空格") == "全角 空格"


def test_strip_cjk_spaces_only_between_cjk():
    assert strip_cjk_spaces("中 文 字") == "中文字"
    assert strip_cjk_spaces("OCR 识别") == "OCR 识别"
    assert strip_cjk_spaces("hello world") == "hello world"


def test_lines_mode_keeps_every_line():
    lines = ["菜单", "打开文件", "另存为", "退出"]
    assert assemble(lines, mode="lines") == "菜单\n打开文件\n另存为\n退出"


def test_paragraph_mode_joins_everything():
    lines = ["这是一段被自动换行拆开的段落，", "第二行继续写。", "第三行结束"]
    assert assemble(lines, mode="paragraph") == "这是一段被自动换行拆开的段落，第二行继续写。第三行结束"


def test_smart_joins_wrapped_long_chinese_line():
    lines = [
        "PaddleOCR 的产线列表包含了文本检测和文本识别两个模块，可以按需调用",
        "在实际使用中，通常先调用检测，再对检测出来的文本框做识别。",
    ]
    out = assemble(lines, mode="smart")
    assert out == lines[0] + lines[1]


def test_smart_keeps_short_menu_items_separate():
    lines = ["文件", "编辑", "视图", "帮助"]
    assert assemble(lines, mode="smart") == "文件\n编辑\n视图\n帮助"


def test_smart_keeps_break_after_terminal_punctuation():
    lines = [
        "第一句话已经结束了，而且这一行足够长足够长足够长足够长。",
        "这是新的一句话，长度也非常长非常长非常长非常长非常长很长。",
    ]
    assert assemble(lines, mode="smart") == "\n".join(lines)


def test_smart_keeps_list_markers():
    lines = [
        "配置项的取值说明如下所示，请注意大小写并且不要写成其它形式",
        "1. limit_type 只能取 max 或 min",
        "2. limit_side_len 是整数",
    ]
    out = assemble(lines, mode="smart")
    assert out.splitlines()[0].startswith("配置项")
    assert "1. limit_type" in out.splitlines()[1]


def test_smart_joins_latin_wrapped_line_with_space():
    lines = [
        "This paragraph was wrapped by the window manager because it is a long line of text",
        "and it continues on the next line.",
    ]
    assert assemble(lines, mode="smart") == (
        "This paragraph was wrapped by the window manager because it is a long line of text"
        " and it continues on the next line."
    )


def test_assemble_drops_empty_lines_and_unknown_mode_raises():
    assert assemble(["", "  ", "abc"], mode="lines") == "abc"
    try:
        assemble(["a"], mode="nope")
    except ValueError as exc:
        assert "nope" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("应当抛出 ValueError")
