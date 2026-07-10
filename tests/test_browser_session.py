import unittest

from taotian_price_tool.browser_launch import BrowserLaunchError, launch_persistent_context_with_fallback
from taotian_price_tool.browser_session import LOGIN_BROWSER_VIEWPORT, LOGIN_BROWSER_WINDOW_SIZE_ARG, LoginBrowserManager


class FakeLocator:
    def __init__(self, text):
        self.text = text

    def inner_text(self, timeout=10000):
        return self.text


class InterruptedThenStablePage:
    def __init__(self):
        self.url = "https://detail.tmall.com/item.htm?id=1060053573566"

    def goto(self, url, wait_until="domcontentloaded", timeout=45000):
        raise RuntimeError(
            'Page.goto: Navigation to "http://a.m.taobao.com/i1060053573566.htm" '
            'is interrupted by another navigation to "https://detail.tmall.com/item.htm?id=1060053573566"'
        )

    def wait_for_load_state(self, state="domcontentloaded", timeout=10000):
        return None

    def wait_for_timeout(self, timeout):
        return None

    def title(self):
        return "Redmi Buds 6 入耳式耳机"

    def locator(self, selector):
        return FakeLocator("Redmi Buds 6 入耳式耳机\n￥\n159")


class FakeBrowserType:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []

    def launch_persistent_context(self, **kwargs):
        channel = kwargs.get("channel")
        self.calls.append(channel or "bundled_chromium")
        if channel in self.failures or (channel is None and None in self.failures):
            raise RuntimeError(f"{channel or 'bundled'} unavailable")
        return {"channel": channel}


class LoginBrowserSessionTests(unittest.TestCase):
    def test_login_browser_uses_desktop_width_for_qr_login(self):
        self.assertGreaterEqual(LOGIN_BROWSER_VIEWPORT["width"], 1000)
        self.assertGreaterEqual(LOGIN_BROWSER_VIEWPORT["height"], 760)
        self.assertIn(str(LOGIN_BROWSER_VIEWPORT["width"]), LOGIN_BROWSER_WINDOW_SIZE_ARG)
        self.assertIn(str(LOGIN_BROWSER_VIEWPORT["height"]), LOGIN_BROWSER_WINDOW_SIZE_ARG)

    def test_interrupted_navigation_still_captures_stable_detail_page(self):
        manager = LoginBrowserManager(user_data_dir="unused")

        capture = manager._fetch_with_page(InterruptedThenStablePage(), "http://a.m.taobao.com/i1060053573566.htm")

        self.assertIn("detail.tmall.com", capture.final_url)
        self.assertIn("Redmi Buds", capture.visible_text)
        self.assertIn("interrupted by another navigation", capture.error)

    def test_launch_prefers_system_chrome(self):
        browser = FakeBrowserType()

        context, source = launch_persistent_context_with_fallback(
            browser,
            user_data_dir="profile",
            headless=False,
            viewport=LOGIN_BROWSER_VIEWPORT,
            locale="zh-CN",
            args=[],
        )

        self.assertEqual("chrome", source)
        self.assertEqual({"channel": "chrome"}, context)
        self.assertEqual(["chrome"], browser.calls)

    def test_launch_falls_back_to_edge_after_chrome_failure(self):
        browser = FakeBrowserType(failures={"chrome"})

        context, source = launch_persistent_context_with_fallback(
            browser,
            user_data_dir="profile",
            headless=False,
            viewport=LOGIN_BROWSER_VIEWPORT,
            locale="zh-CN",
            args=[],
        )

        self.assertEqual("msedge", source)
        self.assertEqual({"channel": "msedge"}, context)
        self.assertEqual(["chrome", "msedge"], browser.calls)

    def test_launch_falls_back_to_bundled_chromium_after_system_failures(self):
        browser = FakeBrowserType(failures={"chrome", "msedge"})

        context, source = launch_persistent_context_with_fallback(
            browser,
            user_data_dir="profile",
            headless=False,
            viewport=LOGIN_BROWSER_VIEWPORT,
            locale="zh-CN",
            args=[],
        )

        self.assertEqual("bundled_chromium", source)
        self.assertEqual({"channel": None}, context)
        self.assertEqual(["chrome", "msedge", "bundled_chromium"], browser.calls)

    def test_launch_without_bundled_browser_returns_readable_error(self):
        browser = FakeBrowserType(failures={"chrome", "msedge"})

        with self.assertRaisesRegex(BrowserLaunchError, "请安装 Chrome/Edge 或使用 full 版"):
            launch_persistent_context_with_fallback(
                browser,
                user_data_dir="profile",
                headless=False,
                viewport=LOGIN_BROWSER_VIEWPORT,
                locale="zh-CN",
                args=[],
                allow_bundled=False,
            )


if __name__ == "__main__":
    unittest.main()
