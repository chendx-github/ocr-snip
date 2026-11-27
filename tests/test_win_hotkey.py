"""Windows 热键解析与虚拟键码映射（纯逻辑，可在 Linux 上测）。"""

import pytest

from ocrsnip.win_hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    key_to_vk,
    parse_hotkey_win,
)


def test_parse_ctrl_alt_q():
    mods, vk = parse_hotkey_win("ctrl+alt+q")
    assert mods == MOD_NOREPEAT | MOD_CONTROL | MOD_ALT
    assert vk == ord("Q")


def test_parse_super_shift_s():
    mods, vk = parse_hotkey_win("super+shift+s")
    assert mods & MOD_WIN and mods & MOD_SHIFT
    assert vk == ord("S")


def test_parse_printscreen_without_modifiers():
    mods, vk = parse_hotkey_win("print")
    assert mods == MOD_NOREPEAT
    assert vk == 0x2C  # VK_SNAPSHOT


def test_function_keys_and_digits():
    assert key_to_vk("f1") == 0x70
    assert key_to_vk("F12") == 0x7B
    assert key_to_vk("5") == ord("5")
    assert key_to_vk("space") == 0x20


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        parse_hotkey_win("ctrl+alt+不存在的键")
    with pytest.raises(ValueError):
        key_to_vk("f25")
    with pytest.raises(ValueError):
        parse_hotkey_win("hyper+q")
