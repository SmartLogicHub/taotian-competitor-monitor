from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def normalize_feishu_link_value(value: Any) -> str:
    """Return a comparable URL/text value from Feishu text or URL cells."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("link", "url", "text"):
            text = normalize_feishu_link_value(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        for item in value:
            text = normalize_feishu_link_value(item)
            if text:
                return text
        return ""
    return str(value).strip()


def extract_taobao_item_id(url: str) -> str:
    text = normalize_feishu_link_value(url)
    if not text:
        return ""
    patterns = [
        r"[?&](?:id|itemId|item_id)=(\d+)",
        r"/i(\d+)\.htm",
        r"/item/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def normalize_record_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if value <= 0:
            return ""
        timestamp = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
        except (OSError, OverflowError, ValueError):
            return str(value).strip()
    return str(value).strip()


def normalize_url_for_dedupe(url: str) -> str:
    text = normalize_feishu_link_value(url)
    if not text:
        return ""
    if not re.match(r"^[a-z]+://", text, flags=re.IGNORECASE):
        text = "https://" + text
    try:
        parsed = urlsplit(text)
    except ValueError:
        return text.lower().strip().rstrip("/")
    query_parts = []
    for part in parsed.query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0].lower()
        if key in {"id", "itemid", "item_id"}:
            query_parts.append(part)
    query = "&".join(query_parts)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), query, "")).strip()


def build_dedup_key(
    *,
    link: Any = "",
    date: Any = "",
    brand: Any = "",
    item_id: Any = "",
) -> tuple[str, str, str] | None:
    normalized_date = normalize_record_date(date)
    item_text = str(item_id or "").strip() or extract_taobao_item_id(normalize_feishu_link_value(link))
    if item_text and normalized_date:
        return ("item", item_text, normalized_date)
    normalized_link = normalize_url_for_dedupe(normalize_feishu_link_value(link))
    if normalized_link and normalized_date:
        return ("url", normalized_link, normalized_date)
    brand_text = str(brand or "").strip()
    if brand_text and not normalized_link and not normalized_date:
        return ("brand_only", brand_text, "")
    return None
