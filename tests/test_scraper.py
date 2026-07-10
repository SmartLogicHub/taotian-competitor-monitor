import unittest
from types import SimpleNamespace

from taotian_price_tool.scraper import PlaywrightProductScraper, ProductPageParser


class FakeBrowserSession:
    def __init__(self, capture):
        self.capture = capture
        self.urls = []

    def fetch_page(self, url):
        self.urls.append(url)
        return self.capture


class ProductPageParserTests(unittest.TestCase):
    def test_parses_visible_price_and_title_from_detail_text(self):
        text = "\n".join(
            [
                "小米官方旗舰店",
                "小米耳机红米Buds6蓝牙无线耳机49dB降噪体验42h长续航双设备连接",
                "已售 800+",
                "￥",
                "159",
                "颜色分类",
            ]
        )

        snapshot = ProductPageParser().parse(text)

        self.assertEqual("success", snapshot.status)
        self.assertEqual("159", snapshot.price)
        self.assertIn("小米耳机", snapshot.title)

    def test_detects_verification_page(self):
        text = "阿里巴巴集团 | 身份验证 正在检测你的安全产品 短信验证"

        snapshot = ProductPageParser().parse(text)

        self.assertEqual("needs_verification", snapshot.status)
        self.assertIn("验证", snapshot.note)

    def test_detects_login_redirect_from_final_url(self):
        snapshot = ProductPageParser().parse(
            "",
            final_url="https://login.taobao.com/havanaone/login/login.htm?redirectURL=https%3A%2F%2Fa.m.taobao.com%2Fi1059057030771.htm",
            page_title="淘宝登录",
        )

        self.assertEqual("needs_verification", snapshot.status)
        self.assertIn("登录", snapshot.note)

    def test_detects_passport_verification_url(self):
        snapshot = ProductPageParser().parse(
            "",
            final_url="https://passport.taobao.com/iv/verify_modes.htm?htoken=abc&firstIn=true",
            page_title="身份验证",
        )

        self.assertEqual("needs_verification", snapshot.status)
        self.assertIn("验证", snapshot.note)

    def test_detects_off_shelf_product_page(self):
        snapshot = ProductPageParser().parse(
            "很抱歉，您查看的商品已下架，可能被转移或删除",
            final_url="https://detail.tmall.com/item.htm?id=404",
            page_title="商品不存在",
        )

        self.assertEqual("off_shelf", snapshot.status)
        self.assertIn("下架", snapshot.note)

    def test_detects_taobao_noitem_error_url_as_off_shelf(self):
        snapshot = ProductPageParser().parse(
            "",
            final_url="https://error.item.taobao.com/error/noitem?type=noitem&itemid=1060464732667",
            page_title="淘宝错误页",
        )

        self.assertEqual("off_shelf", snapshot.status)
        self.assertIn("下架", snapshot.note)

    def test_returns_failed_when_price_is_missing(self):
        snapshot = ProductPageParser().parse("商品详情 暂时无法加载")

        self.assertEqual("failed", snapshot.status)
        self.assertIn("价格", snapshot.note)


class PlaywrightProductScraperTests(unittest.TestCase):
    def test_uses_shared_browser_session_to_fetch_product_page(self):
        browser = FakeBrowserSession(
            SimpleNamespace(
                visible_text="Redmi Buds 6 入耳式耳机\n￥\n159",
                final_url="https://detail.tmall.com/item.htm?id=1",
                page_title="Redmi Buds 6 入耳式耳机",
                error="",
            )
        )
        scraper = PlaywrightProductScraper(browser_session=browser)

        snapshot = scraper.fetch("https://detail.tmall.com/item.htm?id=1")

        self.assertEqual(["https://detail.tmall.com/item.htm?id=1"], browser.urls)
        self.assertEqual("success", snapshot.status)
        self.assertEqual("159", snapshot.price)

    def test_interrupted_navigation_to_passport_verification_is_not_marked_failed(self):
        browser = FakeBrowserSession(
            SimpleNamespace(
                visible_text="",
                final_url="http://a.m.taobao.com/i1060464732667.htm",
                page_title="",
                error='Page.goto: Navigation is interrupted by another navigation to "https://passport.taobao.com/iv/verify_modes.htm?htoken=abc"',
            )
        )
        scraper = PlaywrightProductScraper(browser_session=browser)

        snapshot = scraper.fetch("http://a.m.taobao.com/i1060464732667.htm")

        self.assertEqual("needs_verification", snapshot.status)
        self.assertIn("验证", snapshot.note)

    def test_interrupted_navigation_to_noitem_error_is_marked_off_shelf(self):
        browser = FakeBrowserSession(
            SimpleNamespace(
                visible_text="",
                final_url="http://a.m.taobao.com/i1060464732667.htm",
                page_title="",
                error='Page.goto: Navigation is interrupted by another navigation to "https://error.item.taobao.com/error/noitem?type=noitem&itemid=1060464732667"',
            )
        )
        scraper = PlaywrightProductScraper(browser_session=browser)

        snapshot = scraper.fetch("http://a.m.taobao.com/i1060464732667.htm")

        self.assertEqual("off_shelf", snapshot.status)
        self.assertIn("下架", snapshot.note)


if __name__ == "__main__":
    unittest.main()
