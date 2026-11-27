from pathlib import Path

from ocrsnip.config import Config


def test_defaults_are_speed_first():
    cfg = Config.load(Path("/nonexistent/ocrsnip.toml"))
    assert cfg.hotkey == "ctrl+alt+q"
    assert cfg.ocr.det_limit_type == "max"
    assert cfg.ocr.use_cls is False
    assert cfg.post.mode == "smart"
    assert cfg.warnings == []


def test_toml_overrides_and_unknown_key_warns(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
hotkey = "super+shift+s"
[ocr]
threads = 4
det_limit_side_len = 1536
[post]
mode = "lines"
[ui]
dim = 0.9
""",
        encoding="utf-8",
    )
    cfg = Config.load(path)
    assert cfg.hotkey == "super+shift+s"
    assert cfg.ocr.threads == 4
    assert cfg.ocr.det_limit_side_len == 1536
    assert cfg.post.mode == "lines"
    assert cfg.ui.dim == 0.9


def test_unknown_and_invalid_values_are_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
nonsense = 1
[post]
mode = "nope"
[ocr]
threads = 999
""",
        encoding="utf-8",
    )
    cfg = Config.load(path)
    assert any("nonsense" in w for w in cfg.warnings)
    assert cfg.post.mode == "smart"  # 回退
    assert cfg.ocr.threads == 32  # 夹到上限


def test_broken_toml_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this is not toml =", encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.hotkey == "ctrl+alt+q"
    assert cfg.warnings
