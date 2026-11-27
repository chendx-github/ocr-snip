import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ocrsnip.config import OcrConfig, PostConfig
from ocrsnip.ocr import OcrEngine

FIXTURE = Path(__file__).parent / "fixtures" / "sample_zh.png"


def _fixture_bgr() -> np.ndarray:
    """用预渲染的 PNG：本机 GTK3 先于 PIL 导入时 PIL 的中文字体渲染会异常，见 .wiki/。"""
    with Image.open(FIXTURE) as img:
        return np.array(img.convert("RGB"))[:, :, ::-1].copy()


@pytest.fixture(scope="module")
def engine() -> OcrEngine:
    eng = OcrEngine(OcrConfig(threads=4), PostConfig())
    eng.warmup()
    return eng


def test_recognizes_chinese_and_latin(engine: OcrEngine):
    result = engine.recognize(_fixture_bgr())
    assert "识别测试" in result.text
    assert "2026" in result.text
    assert "clipboard" in result.text.lower()
    assert len(result.lines) >= 2


def test_small_crop_stays_fast(engine: OcrEngine):
    """回归防线：det 的 limit_type 一旦被改回 min，这里会慢 5-10 倍。"""
    img = _fixture_bgr()[:60, :340]
    started = time.perf_counter()
    for _ in range(3):
        engine.recognize(img)
    avg_ms = (time.perf_counter() - started) * 1000 / 3
    assert avg_ms < 400, f"小图平均 {avg_ms:.0f} ms，太慢了"


def test_blank_image_returns_empty(engine: OcrEngine):
    img = np.full((80, 320, 3), 255, dtype=np.uint8)
    result = engine.recognize(img)
    assert result.text == ""
    assert result.lines == []


def test_lines_mode_keeps_two_lines(engine: OcrEngine):
    engine.post.mode = "lines"
    try:
        result = engine.recognize(_fixture_bgr())
        assert "\n" in result.text
        assert result.text.splitlines()[0].startswith("快捷截屏")
    finally:
        engine.post.mode = "smart"
