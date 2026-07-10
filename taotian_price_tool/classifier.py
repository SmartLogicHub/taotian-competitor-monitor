from __future__ import annotations

from dataclasses import dataclass


ALLOWED_SHAPES = ("半入耳", "入耳式", "耳夹式", "头戴式", "挂脖式", "挂耳式")
DEFAULT_SHAPE = "入耳式"


@dataclass(frozen=True)
class ShapeResult:
    shape: str
    reason: str


def normalize_shape(shape: str) -> str:
    text = shape.strip().lower()
    if not text or "未知" in text or "待确认" in text:
        return DEFAULT_SHAPE
    if "半入耳" in text:
        return "半入耳"
    if "头戴" in text or "headphone" in text:
        return "头戴式"
    if "挂脖" in text or "颈挂" in text or "脖挂" in text or "neckband" in text:
        return "挂脖式"
    if "耳夹" in text or "夹耳" in text or "clip" in text:
        return "耳夹式"
    if "骨传导" in text or "挂耳" in text or "耳挂" in text or "earhook" in text:
        return "挂耳式"
    if "入耳" in text or "耳塞" in text or "buds" in text or "tws" in text:
        return "入耳式"
    return DEFAULT_SHAPE


class HeuristicShapeClassifier:
    def classify(self, title: str, detail_text: str = "") -> ShapeResult:
        text = f"{title} {detail_text}".lower()
        shape = normalize_shape(text)
        if shape != DEFAULT_SHAPE or any(token in text for token in ("入耳", "耳塞", "buds", "tws")):
            return ShapeResult(shape, f"标题/参数匹配到{shape}线索")
        return ShapeResult(DEFAULT_SHAPE, "未识别到明确形态线索，按默认入耳式填写")
