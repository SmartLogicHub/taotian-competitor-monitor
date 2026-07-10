"""Excel 数据结构和归档导出"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


@dataclass(frozen=True)
class LinkRow:
    row_number: int
    url: str


@dataclass(frozen=True)
class RowResult:
    row_number: int
    price: str
    shape: str
    status: str
    note: str = ""


@dataclass(frozen=True)
class ArchiveItem:
    """归档导出用的完整数据"""
    row: int
    brand: str
    on_sale_date: str
    goods_link: str
    goods_name: str
    shape: str
    price: str
    status: str
    note: str = ""


ARCHIVE_HEADERS = [
    "行号", "品牌", "上架日期", "链接", "商品名称",
    "耳机形态", "价格", "采集状态", "备注",
]


def write_archive(
    items: list[ArchiveItem],
    *,
    output_dir: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """生成归档 Excel 副本"""
    output_dir = Path(output_dir) if output_dir else Path.home() / "Downloads"
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"竞品监控归档_{timestamp}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "采集结果"
    ws.append(ARCHIVE_HEADERS)

    for item in items:
        ws.append([
            item.row,
            item.brand,
            item.on_sale_date,
            item.goods_link,
            item.goods_name,
            item.shape,
            item.price,
            item.status,
            item.note,
        ])

    output_dir.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()
    return output_path
