from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductSnapshot:
    status: str
    title: str = ""
    price: str = ""
    detail_text: str = ""
    shop: str = ""
    note: str = ""

