"""OCR 引擎封装（RapidOCR + ONNX Runtime，PP-OCRv6 小模型，随包自带）。"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .config import OcrConfig, PostConfig
from .postprocess import assemble


@dataclass
class OcrLine:
    text: str
    score: float
    box: tuple[int, int, int, int]


@dataclass
class OcrResult:
    text: str
    lines: list[OcrLine]
    elapsed_ms: float
    raw_line_count: int

    @property
    def chars(self) -> int:
        return len(self.text)


class OcrEngine:
    """构造一次、常驻复用：模型加载约 15ms，推理前不需要再预热。"""

    def __init__(self, cfg: OcrConfig, post: PostConfig) -> None:
        self.cfg = cfg
        self.post = post
        self._engine = None

    # ---- 初始化 ------------------------------------------------------
    def load(self):
        if self._engine is not None:
            return self._engine
        from rapidocr import RapidOCR  # 延迟导入：daemon 启动不用等 onnxruntime

        params = {
            # —— 决定性的一行：小选区不放大 ——
            "Det.limit_type": self.cfg.det_limit_type,
            "Det.limit_side_len": self.cfg.det_limit_side_len,
            "Global.use_cls": self.cfg.use_cls,
            "Global.use_vertical_padding": self.cfg.vertical_padding,
            "Global.text_score": self.cfg.min_score,
            "Global.log_level": "error",
            "Rec.rec_batch_num": self.cfg.rec_batch_num,
            "EngineConfig.onnxruntime.intra_op_num_threads": self.cfg.threads,
            "EngineConfig.onnxruntime.enable_cpu_mem_arena": self.cfg.cpu_mem_arena,
        }
        self._engine = RapidOCR(params=params)
        return self._engine

    def warmup(self) -> None:
        """真实跑一次推理，把 onnxruntime 的算子/线程池都热起来。"""
        engine = self.load()
        img = np.full((64, 320, 3), 255, dtype=np.uint8)
        engine(img)

    # ---- 推理 --------------------------------------------------------
    def recognize(self, bgr: np.ndarray) -> OcrResult:
        engine = self.load()
        started = time.perf_counter()
        out = engine(bgr)
        elapsed_ms = (time.perf_counter() - started) * 1000

        texts = list(getattr(out, "txts", None) or [])
        scores = list(getattr(out, "scores", None) or [])
        boxes: list[OcrLine] = []
        for index, text in enumerate(texts):
            score = float(scores[index]) if index < len(scores) else 0.0
            if score < self.cfg.min_score:
                continue
            box = _bbox(getattr(out, "boxes", None), index, bgr.shape)
            boxes.append(OcrLine(text=text, score=score, box=box))

        boxes.sort(key=lambda line: (line.box[1] // 8, line.box[0]))
        text = assemble(
            [line.text for line in boxes],
            mode=self.post.mode,
            do_strip_cjk_spaces=self.post.strip_cjk_spaces,
        )
        return OcrResult(
            text=text, lines=boxes, elapsed_ms=elapsed_ms, raw_line_count=len(texts)
        )


def _bbox(raw, index: int, shape) -> tuple[int, int, int, int]:
    height, width = shape[0], shape[1]
    try:
        points = raw[index]
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
        x1, y1 = min(width, int(max(xs))), min(height, int(max(ys)))
        return x0, y0, max(0, x1 - x0), max(0, y1 - y0)
    except Exception:
        return 0, 0, width, height
