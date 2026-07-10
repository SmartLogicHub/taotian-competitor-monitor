from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any


class DailyResultCache:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def get(self, url: str, *, today: date | None = None) -> dict[str, Any] | None:
        today = today or date.today()
        data = self._load()
        item = data.get(url)
        if not item or item.get("date") != today.isoformat():
            return None
        result = item.get("result")
        return result if isinstance(result, dict) else None

    def set(self, url: str, result: dict[str, Any], *, today: date | None = None) -> None:
        today = today or date.today()
        data = self._load()
        data[url] = {"date": today.isoformat(), "result": result}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> int:
        """清除所有缓存条目，返回清除的条数。"""
        data = self._load()
        count = len(data)
        if self.path.exists():
            self.path.unlink()
        return count

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}

