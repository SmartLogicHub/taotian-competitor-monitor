from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
import queue
import re
import threading
import time
from typing import Any, Iterable

from .browser_launch import launch_persistent_context_with_fallback


BI_WORKTABLE_URL = "https://mbz.ecbis.cn/workTable/newMonitoring"
BI_API_BASE = "https://biplugs.ecbis.cn/prod/newGoodsMonitor"
SHOP_TASK_LIST_ENDPOINT = f"{BI_API_BASE}/shopTaskList"
NEW_GOODS_LIST_ENDPOINT = f"{BI_API_BASE}/newGoodsList"


STORE_NAME_TO_BRAND = {
    "sanag塞那旗舰店": "塞那",
    "baseus倍思旗舰店": "倍思",
    "SHOKZ韶音旗舰店": "韶音",
    "金运旗舰店": "金运",
    "1MORE万魔官方旗舰店": "万魔",
    "SOAIY旗舰店": "索爱",
    "iKF旗舰店": "ikf",
    "唐麦旗舰店": "唐麦",
    "水月雨旗舰店": "水月雨",
    "soundcore声阔旗舰店": "声阔",
    "JBL耳机旗舰店": "JBL",
    "索尼官方旗舰店": "索尼官方",
    "索尼影音旗舰店": "索尼影音",
    "绿联数码旗舰店": "绿联",
    "华为官方旗舰店": "华为",
    "小米官方旗舰店": "小米",
    "索爱麒麟专卖店": "索爱麒麟专卖店",
    "索爱数码旗舰店": "索爱数码旗舰店",
    "索爱影音旗舰店": "索爱影音旗舰店",
    "深圳索爱专卖店": "深圳索爱专卖店",
    "漫步者靓敏专卖店": "漫步者靓敏专卖店",
    "漫步者上海专卖店": "漫步者上海专卖店",
    "漫步者音派专卖店": "漫步者音派专卖店",
    "漫步者花再旗舰店": "漫步者花再旗舰店",
    "漫步者广州专卖店": "漫步者广州专卖店",
    "漫步者音为爱专卖店": "漫步者音为爱专卖店",
    "瓷音未来影音旗舰店": "瓷音未来影音旗舰店",
    "迈从官方旗舰店": "迈从官方旗舰店",
    "西伯利亚旗舰店": "西伯利亚旗舰店",
    "罗技G官方旗舰店": "罗技G官方旗舰店",
    "雷蛇官方旗舰店": "雷蛇官方旗舰店",
    "ASUS华硕旗舰店": "ASUS华硕旗舰店",
    "HYPERX旗舰店": "HYPERX旗舰店",
    "觅声旗舰店": "觅声旗舰店",
    "ROG旗舰店": "ROG旗舰店",
    "得胜旗舰店": "得胜旗舰店",
    "十度旗舰店": "十度旗舰店",
    "得力官方旗舰店": "得力官方旗舰店",
    "易相随旗舰店": "易相随旗舰店",
    "asing大行旗舰店": "asing大行旗舰店",
}

SKIPPED_SHOPS = {"漫步者官方旗舰店"}


@dataclass(frozen=True)
class BiImportConfig:
    start_date: str = ""
    end_date: str = ""
    days_type: int = 7
    platform: str = "TX"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "BiImportConfig":
        days_type = int(payload.get("days_type") or payload.get("daysType") or 7)
        end_date = str(payload.get("end_date") or payload.get("endDate") or "").strip()
        start_date = str(payload.get("start_date") or payload.get("startDate") or "").strip()
        if end_date and not start_date:
            start_date = _start_date_from_days(end_date, days_type)
        return cls(start_date=start_date, end_date=end_date, days_type=days_type)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"platform": self.platform, "daysType": self.days_type}
        if self.start_date:
            payload["startDate"] = self.start_date
        if self.end_date:
            payload["endDate"] = self.end_date
        return payload


@dataclass(frozen=True)
class BiTemplateItem:
    brand: str
    shop_name: str
    goods_name: str
    goods_link: str
    item_id: str
    fetch_link: str = ""
    on_sale_time: str = ""
    source_price: str = ""
    cate_name: str = ""
    cate_path_name: str = ""
    note: str = ""

    @property
    def display_date(self) -> str:
        return format_on_sale_date(self.on_sale_time)


@dataclass(frozen=True)
class BiImportResult:
    import_count: int = 0
    earphone_count: int = 0
    items: list[BiTemplateItem] = field(default_factory=list)
    skipped_shop_count: int = 0
    deduped_count: int = 0
    message: str = ""
    checked_brands: list[str] = field(default_factory=list)  # v8: 所有受检品牌（含无上新的）


@dataclass(frozen=True)
class _BiRequestTask:
    endpoint: str
    payload: dict[str, Any]
    result_queue: queue.Queue[Any]


class BiBrowserSession:
    """Keeps one visible BI browser profile alive and runs BI API calls in that session."""

    def __init__(
        self,
        *,
        user_data_dir: Path,
        login_url: str = BI_WORKTABLE_URL,
    ) -> None:
        self.user_data_dir = Path(user_data_dir)
        self.login_url = login_url
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._tasks: queue.Queue[_BiRequestTask | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._last_error = ""
        self._current_url = ""
        self._browser_source = "unavailable"

    def open(self) -> dict[str, str]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"status": "already_open", "message": "边界BI浏览器已经打开"}
            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            self._last_error = ""
            self._current_url = ""
            self._browser_source = "unavailable"
            self._stop_event = threading.Event()
            self._ready_event = threading.Event()
            self._tasks = queue.Queue()
            self._thread = threading.Thread(target=self._run, name="bi-browser-session", daemon=True)
            self._thread.start()
            return {"status": "opened", "message": "已打开边界BI浏览器，请手动登录后再读取新品"}

    def close(self, timeout: float = 3.0) -> None:
        thread: threading.Thread | None
        with self._lock:
            self._stop_event.set()
            thread = self._thread
            try:
                self._tasks.put_nowait(None)
            except Exception:
                pass
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def status(self) -> dict[str, str | bool]:
        thread = self._thread
        return {
            "running": bool(thread and thread.is_alive()),
            "last_error": self._last_error,
            "profile_dir": str(self.user_data_dir),
            "current_url": self._current_url,
            "browser_source": self._browser_source,
        }

    def request_json(self, endpoint: str, payload: dict[str, Any], *, timeout: float = 75.0) -> dict[str, Any]:
        self.open()
        if not self._ready_event.wait(timeout=min(timeout, 20.0)):
            raise RuntimeError(self._last_error or "边界BI浏览器启动超时")
        if self._last_error and not self.status().get("running"):
            raise RuntimeError(self._last_error)

        result_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
        self._tasks.put(_BiRequestTask(endpoint=endpoint, payload=payload, result_queue=result_queue))
        try:
            result = result_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise RuntimeError("边界BI浏览器响应超时，请检查是否需要重新登录") from exc
        if isinstance(result, Exception):
            raise result
        return result

    def _run(self) -> None:  # pragma: no cover - browser integration
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                context, browser_source = launch_persistent_context_with_fallback(
                    playwright.chromium,
                    user_data_dir=str(self.user_data_dir),
                    headless=False,
                    viewport={"width": 1360, "height": 900},
                    locale="zh-CN",
                    args=["--window-size=1360,900"],
                )
                self._browser_source = browser_source
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    try:
                        page.goto(self.login_url, wait_until="domcontentloaded", timeout=45000)
                        self._current_url = page.url
                    except Exception as exc:
                        self._last_error = str(exc)
                    self._ready_event.set()

                    while not self._stop_event.is_set():
                        if not context.pages:
                            break
                        page = page if not page.is_closed() else context.pages[0]
                        try:
                            task = self._tasks.get(timeout=0.2)
                        except queue.Empty:
                            time.sleep(0.1)
                            continue
                        if task is None:
                            break
                        try:
                            task.result_queue.put(self._request_with_page(page, task.endpoint, task.payload))
                        except Exception as exc:
                            task.result_queue.put(exc)
                finally:
                    self._ready_event.set()
                    context.close()
        except Exception as exc:
            self._last_error = str(exc)
            self._ready_event.set()

    def _request_with_page(self, page, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        result = page.evaluate(
            """
            async ({ endpoint, payload }) => {
              const res = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify(payload)
              });
              return { status: res.status, text: await res.text(), currentUrl: location.href };
            }
            """,
            {"endpoint": endpoint, "payload": payload},
        )
        self._current_url = str(result.get("currentUrl") or "")
        text = str(result.get("text") or "")
        if int(result.get("status") or 0) >= 400:
            raise RuntimeError(f"边界BI接口请求失败：HTTP {result.get('status')} {text[:300]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("边界BI返回内容不是 JSON，请检查是否仍在登录页") from exc


class EarphoneGoodsFilter:
    category_keywords = ("蓝牙耳机", "无线耳机", "耳机", "耳麦")
    title_keywords = (
        "耳机",
        "耳麦",
        "耳塞",
        "无线耳机",
        "buds",
        "airpods",
        "头戴",
        "入耳",
        "半入耳",
        "耳夹",
        "挂耳",
        "开放式",
        "开放式耳机",
        "降噪耳机",
    )
    excluded_keywords = (
        "手机",
        "空调",
        "鼻毛修剪器",
        "剃须刀",
        "充电器",
        "数据线",
        "保护壳",
        "平板",
        "手表",
        "音箱",
        "音响",
        "蓝牙音箱",
        "智能音箱",
        "speaker",
        "soundbar",
        "回音壁",
        "低音炮",
        "桌面音响",
    )

    def is_earphone(self, payload: dict[str, Any]) -> bool:
        cate_text = f"{payload.get('cateName', '')} {payload.get('catePathName', '')}".lower()
        title_text = str(payload.get("goodsName", "")).lower()
        combined = f"{cate_text} {title_text}"
        if any(keyword.lower() in combined for keyword in self.excluded_keywords):
            return False
        if any(keyword.lower() in cate_text for keyword in self.category_keywords):
            return True
        return any(keyword.lower() in title_text for keyword in self.title_keywords)


class BiClient:
    def __init__(
        self,
        *,
        session: Any,
        goods_filter: EarphoneGoodsFilter | None = None,
    ) -> None:
        self.session = session
        self.goods_filter = goods_filter or EarphoneGoodsFilter()

    def import_goods(self, config: BiImportConfig, *, template_brands: Iterable[str] | None = None) -> BiImportResult:
        base_payload = config.to_payload()
        shops_payload = self.session.request_json(SHOP_TASK_LIST_ENDPOINT, base_payload)
        shops = _extract_list(shops_payload)
        items: list[BiTemplateItem] = []
        seen_records: set[tuple[str, str, str]] = set()
        import_count = 0
        skipped_shop_count = 0
        deduped_count = 0
        checked_brands: set[str] = set()

        for shop in shops:
            shop_name = str(shop.get("shopName", "")).strip()
            brand = map_shop_to_brand(shop_name, template_brands=template_brands)
            if brand is None:
                if shop_name in SKIPPED_SHOPS:
                    skipped_shop_count += 1
                continue
            checked_brands.add(brand)  # v8: 记录受检品牌（即使该品牌本周期无新品）
            shop_payload = dict(base_payload)
            shop_payload["shopId"] = str(shop.get("shopId", "")).strip()
            goods_payload = self.session.request_json(NEW_GOODS_LIST_ENDPOINT, shop_payload)
            for goods in _extract_list(goods_payload):
                import_count += 1
                goods_link = normalize_goods_link(goods)
                item_id = extract_item_id(goods_link)
                if not goods_link or not item_id:
                    continue
                on_sale_time = str(goods.get("onSaleTime", "")).strip()
                record_key = (shop_name, item_id, on_sale_time)
                if record_key in seen_records:
                    deduped_count += 1
                    continue
                if not self.goods_filter.is_earphone(goods):
                    continue
                seen_records.add(record_key)
                items.append(
                    BiTemplateItem(
                        brand=brand,
                        shop_name=shop_name,
                        goods_name=str(goods.get("goodsName", "")).strip(),
                        goods_link=goods_link,
                        item_id=item_id,
                        fetch_link=standard_fetch_link(item_id),
                        on_sale_time=on_sale_time,
                        source_price=str(goods.get("price", "")).strip(),
                        cate_name=str(goods.get("cateName", "")).strip(),
                        cate_path_name=str(goods.get("catePathName", "")).strip(),
                    )
                )

        return BiImportResult(
            import_count=import_count,
            earphone_count=len(items),
            items=items,
            skipped_shop_count=skipped_shop_count,
            deduped_count=deduped_count,
            message=f"读取 {import_count} 个新品，筛出 {len(items)} 个耳机相关商品，{len(checked_brands)} 个受检品牌",
            checked_brands=list(checked_brands),
        )


def map_shop_to_brand(shop_name: str, *, template_brands: Iterable[str] | None = None) -> str | None:
    normalized = re.sub(r"\s+", "", shop_name)
    if normalized in SKIPPED_SHOPS:
        return None
    for template_brand in template_brands or []:
        candidate = str(template_brand or "").strip()
        if candidate and re.sub(r"\s+", "", candidate) == normalized:
            return candidate
    for source, brand in STORE_NAME_TO_BRAND.items():
        if re.sub(r"\s+", "", source) == normalized:
            return brand
    return None


def normalize_goods_link(payload: dict[str, Any]) -> str:
    goods_link = str(payload.get("goodsLink") or "").strip()
    if _looks_like_picture_url(goods_link):
        return ""
    item_id = extract_item_id(goods_link) if goods_link and _looks_like_item_url(goods_link) else ""
    goods_id = str(payload.get("goodsId") or payload.get("itemId") or payload.get("itemid") or "").strip()
    if not item_id and re.fullmatch(r"\d{6,}", goods_id):
        item_id = goods_id
    if item_id:
        return standard_fetch_link(item_id)
    return ""


def standard_fetch_link(item_id: str) -> str:
    return f"https://detail.tmall.com/item.htm?id={item_id}" if item_id else ""


def extract_item_id(text: str) -> str:
    if not text:
        return ""
    patterns = (
        r"/i(\d+)\.htm",
        r"[?&](?:id|itemid|itemId)=(\d+)",
        r"\bitemid=(\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def format_on_sale_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            parsed = datetime.strptime(text[:10] if fmt != "%Y年%m月%d日" else text, fmt)
            return f"{parsed.month}月{parsed.day}"
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})月(\d{1,2})", text)
    if match:
        return f"{int(match.group(1))}月{int(match.group(2))}"
    return text


def _start_date_from_days(end_date: str, days_type: int) -> str:
    try:
        parsed = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return ""
    return (parsed - timedelta(days=max(days_type, 1) - 1)).strftime("%Y-%m-%d")


def _looks_like_picture_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "img.alicdn.com" in lowered
        or "uploaded" in lowered
        or lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
    )


def _looks_like_item_url(url: str) -> bool:
    lowered = url.lower()
    return (
        ("taobao.com" in lowered or "tmall.com" in lowered)
        and not _looks_like_picture_url(url)
        and ("item" in lowered or "/i" in lowered or "noitem" in lowered)
    )


def _extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("records", "list", "rows", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    for key in ("records", "list", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
