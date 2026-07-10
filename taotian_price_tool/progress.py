from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class RowProgress:
    row: int
    url: str
    status: str
    price: str = ""
    shape: str = ""
    note: str = ""
    updated_at: str = ""


@dataclass
class TaskProgress:
    source_file: str = ""
    rows: dict[str, RowProgress] = field(default_factory=dict)


class TaskProgressStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> TaskProgress:
        if not self.path.exists():
            return TaskProgress()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = {
            key: RowProgress(**value)
            for key, value in payload.get("rows", {}).items()
        }
        return TaskProgress(source_file=payload.get("source_file", ""), rows=rows)

    def clear(self) -> None:
        """清除所有进度记录。"""
        if self.path.exists():
            self.path.unlink()

    def record_row(
        self,
        *,
        source_file: str,
        row: int,
        url: str,
        status: str,
        price: str = "",
        shape: str = "",
        note: str = "",
    ) -> None:
        progress = self.load()
        progress.source_file = source_file
        progress.rows[str(row)] = RowProgress(
            row=row,
            url=url,
            status=status,
            price=price,
            shape=shape,
            note=note,
            updated_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "source_file": progress.source_file,
                    "rows": {
                        key: asdict(value)
                        for key, value in progress.rows.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

