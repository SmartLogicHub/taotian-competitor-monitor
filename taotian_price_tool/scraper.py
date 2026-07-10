from __future__ import annotations

import re
from pathlib import Path

from .browser_session import PageCapture
from .models import ProductSnapshot


class ProductPageParser:
    verification_keywords = (
        "身份验证",
        "短信验证",
        "滑块",
        "验证码",
        "正在检测你的安全产品",
        "扫码登录",
        "密码登录",
        "登录淘宝",
        "请登录",
    )
    verification_url_keywords = (
        "login.taobao.com",
        "login.tmall.com",
        "passport.taobao.com",
        "verify_modes",
        "havanaone/login",
        "havanaone/login/continue",
        "login_jump",
        "_____tmd_____",
    )
    off_shelf_keywords = (
        "error.item.taobao.com",
        "/error/noitem",
        "type=noitem",
        "商品已下架",
        "宝贝不存在",
        "商品不存在",
        "该商品已失效",
        "该宝贝已失效",
        "已卖光",
        "页面不存在",
        "item not found",
        "not found",
    )

    def parse(self, visible_text: str, *, final_url: str = "", page_title: str = "") -> ProductSnapshot:
        text = visible_text.strip()
        page_state_text = "\n".join(part for part in (page_title, final_url, text) if part)
        lowered_state = page_state_text.lower()
        if any(keyword.lower() in lowered_state for keyword in self.verification_url_keywords):
            return ProductSnapshot(
                status="needs_verification",
                detail_text=text,
                note="页面进入登录/身份验证，需要人工处理",
            )
        if any(keyword.lower() in lowered_state for keyword in self.off_shelf_keywords):
            return ProductSnapshot(
                status="off_shelf",
                detail_text=text,
                note="详情页提示商品已下架",
            )
        if any(keyword.lower() in lowered_state for keyword in self.verification_keywords):
            return ProductSnapshot(
                status="needs_verification",
                detail_text=text,
                note="页面进入登录/身份验证，需要人工处理",
            )

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        price = self._extract_price(lines, text)
        title = self._extract_title(lines)
        if not price:
            return ProductSnapshot(
                status="failed",
                title=title,
                detail_text=text,
                note="未能从详情页识别价格",
            )
        return ProductSnapshot(
            status="success",
            title=title,
            price=price,
            detail_text=text,
            note="详情页显示价",
        )

    def _extract_price(self, lines: list[str], text: str) -> str:
        for index, line in enumerate(lines):
            if line == "￥" and index + 1 < len(lines):
                candidate = lines[index + 1].replace(",", "")
                if re.fullmatch(r"\d+(?:\.\d+)?(?:起)?", candidate):
                    return candidate
        match = re.search(r"￥\s*(\d+(?:\.\d+)?(?:起)?)", text)
        return match.group(1) if match else ""

    def _extract_title(self, lines: list[str]) -> str:
        ignored = {"已售 800+", "可开发票", "颜色分类", "套餐类型", "商品详情"}
        for line in lines:
            if line in ignored:
                continue
            if len(line) >= 12 and ("耳机" in line or "buds" in line.lower()):
                return line
        return ""


class PlaywrightProductScraper:
    def __init__(self, *, user_data_dir: Path | None = None, headless: bool = False, browser_session=None) -> None:
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None
        self.headless = headless
        self.browser_session = browser_session
        self.parser = ProductPageParser()

    def fetch(self, url: str) -> ProductSnapshot:
        if self.browser_session is not None:
            return self._snapshot_from_capture(self.browser_session.fetch_page(url))
        if self.user_data_dir is None:
            return ProductSnapshot(status="failed", note="未配置淘宝浏览器会话")
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError:
            return ProductSnapshot(
                status="failed",
                note="未安装 playwright，请先运行 pip install playwright 并安装浏览器。",
            )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                viewport={"width": 1360, "height": 900},
            )
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(5000)
                final_url = page.url
                page_title = page.title()
                try:
                    text = page.locator("body").inner_text(timeout=10000)
                except Exception as exc:
                    return self._snapshot_from_capture(
                        PageCapture(final_url=final_url, page_title=page_title, error=f"页面采集失败：{exc}")
                    )
                return self._snapshot_from_capture(
                    PageCapture(visible_text=text, final_url=final_url, page_title=page_title)
                )
            except Exception as exc:
                return ProductSnapshot(status="failed", note=f"页面采集失败：{exc}")
            finally:
                browser.close()

    def _snapshot_from_capture(self, capture: PageCapture) -> ProductSnapshot:
        page_title = "\n".join(part for part in (capture.page_title, capture.error) if part)
        snapshot = self.parser.parse(
            capture.visible_text,
            final_url=capture.final_url,
            page_title=page_title,
        )
        if capture.error and snapshot.status == "failed":
            return ProductSnapshot(
                status="failed",
                title=snapshot.title,
                detail_text=snapshot.detail_text,
                note=capture.error,
            )
        return snapshot
