from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import request

from .classifier import ALLOWED_SHAPES, HeuristicShapeClassifier, ShapeResult, normalize_shape


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class UrllibJsonTransport:
    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"


class DeepSeekShapeClassifier:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        transport: JsonTransport | None = None,
    ) -> None:
        self.config = DeepSeekConfig(api_key=api_key, model=model)
        self.transport = transport or UrllibJsonTransport()
        self.fallback = HeuristicShapeClassifier()

    def classify(self, title: str, detail_text: str = "") -> ShapeResult:
        if not self.config.api_key:
            return self.fallback.classify(title, detail_text)

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是电商耳机商品形态分类器。必须输出 json，格式为："
                        '{"shape":"入耳式","reason":"简短原因"}。'
                        "shape 只能从这六个值中选择："
                        + "、".join(ALLOWED_SHAPES)
                        + "。不要输出六类之外的标签；不确定时选择最接近的一类。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"商品标题：{title}\n页面参数：{detail_text[:2000]}",
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": 300,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        try:
            response = self.transport.post_json(
                f"{self.config.base_url}/chat/completions",
                headers,
                payload,
            )
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            raw_shape = str(parsed.get("shape", "入耳式"))
            shape = normalize_shape(raw_shape)
            reason = str(parsed.get("reason", "DeepSeek JSON 输出"))
            return ShapeResult(shape, reason)
        except Exception as exc:
            heuristic = self.fallback.classify(title, detail_text)
            return ShapeResult(heuristic.shape, f"{heuristic.reason}；DeepSeek 调用失败：{exc}")
