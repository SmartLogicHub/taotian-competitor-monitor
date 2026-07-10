from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import queue
import random
import threading
import time
from typing import Callable

from .browser_launch import launch_persistent_context_with_fallback


LOGIN_BROWSER_VIEWPORT = {"width": 1180, "height": 820}
LOGIN_BROWSER_WINDOW_SIZE_ARG = f"--window-size={LOGIN_BROWSER_VIEWPORT['width']},{LOGIN_BROWSER_VIEWPORT['height']}"


@dataclass(frozen=True)
class PageCapture:
    visible_text: str = ""
    final_url: str = ""
    page_title: str = ""
    error: str = ""


@dataclass(frozen=True)
class _FetchTask:
    url: str
    result_queue: queue.Queue[PageCapture]


class LoginBrowserManager:
    """Keeps one visible Taobao browser profile alive for login, verification, and collection."""

    def __init__(
        self,
        *,
        user_data_dir: Path,
        login_url: str = "https://login.taobao.com/",
        launcher: Callable[[Path, str, threading.Event], None] | None = None,
    ) -> None:
        self.user_data_dir = Path(user_data_dir)
        self.login_url = login_url
        self.launcher = launcher
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._tasks: queue.Queue[_FetchTask | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._last_error = ""
        self._current_url = ""
        self._browser_source = "unavailable"

    def open(self) -> dict[str, str]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"status": "already_open", "message": "淘宝浏览器已经打开"}

            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            self._last_error = ""
            self._current_url = ""
            self._browser_source = "unavailable"
            self._stop_event = threading.Event()
            self._ready_event = threading.Event()
            self._tasks = queue.Queue()
            self._thread = threading.Thread(target=self._run, name="taobao-browser-session", daemon=True)
            self._thread.start()
            return {"status": "opened", "message": "已打开淘宝浏览器，请扫码或手动登录"}

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

    def fetch_page(self, url: str, *, timeout: float = 75.0) -> PageCapture:
        self.open()
        if not self._ready_event.wait(timeout=min(timeout, 20.0)):
            return PageCapture(error=self._last_error or "淘宝浏览器启动超时")
        if self._last_error and not self.status().get("running"):
            return PageCapture(error=self._last_error)

        result_queue: queue.Queue[PageCapture] = queue.Queue(maxsize=1)
        self._tasks.put(_FetchTask(url=url, result_queue=result_queue))
        try:
            return result_queue.get(timeout=timeout)
        except queue.Empty:
            return PageCapture(error="淘宝浏览器响应超时，请检查页面是否卡在验证或网络异常")

    def status(self) -> dict[str, str | bool]:
        thread = self._thread
        return {
            "running": bool(thread and thread.is_alive()),
            "last_error": self._last_error,
            "profile_dir": str(self.user_data_dir),
            "current_url": self._current_url,
            "browser_source": self._browser_source,
        }

    def _run(self) -> None:
        try:
            if self.launcher:
                self.launcher(self.user_data_dir, self.login_url, self._stop_event)
            else:
                self._run_playwright()
        except Exception as exc:  # pragma: no cover - depends on local browser state
            self._last_error = str(exc)
            self._browser_source = "unavailable"
            self._ready_event.set()

    def _run_playwright(self) -> None:  # pragma: no cover - covered by manual smoke tests
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            context, browser_source = launch_persistent_context_with_fallback(
                playwright.chromium,
                user_data_dir=str(self.user_data_dir),
                headless=False,
                viewport=LOGIN_BROWSER_VIEWPORT,
                locale="zh-CN",
                args=[
                    LOGIN_BROWSER_WINDOW_SIZE_ARG,
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process,TranslateUI,BlinkGenPropertyTrees",
                    "--disable-infobars",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--disable-default-apps",
                    "--disable-component-update",
                    "--disable-domain-reliability",
                    "--disable-breakpad",
                    "--disable-client-side-phishing-detection",
                    "--disable-hang-monitor",
                    "--disable-prompt-on-repost",
                    "--metrics-recording-only",
                    "--mute-audio",
                    "--no-sandbox",
                ],
            )
            self._browser_source = browser_source
            context.add_init_script("""
                // 1. 隐藏 webdriver 标志
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // 2. 伪装 plugins 数组
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const arr = [
                            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
                            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
                            {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
                        ];
                        arr.item = (i) => arr[i] || null;
                        arr.namedItem = (name) => arr.find(p => p.name === name) || null;
                        arr.refresh = () => {};
                        Object.setPrototypeOf(arr, PluginArray.prototype);
                        return arr;
                    }
                });

                // 3. 伪装 mimeTypes
                Object.defineProperty(navigator, 'mimeTypes', {
                    get: () => {
                        const arr = [
                            {type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format'},
                            {type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format'},
                        ];
                        arr.item = (i) => arr[i] || null;
                        arr.namedItem = (name) => arr.find(m => m.type === name) || null;
                        Object.setPrototypeOf(arr, MimeTypeArray.prototype);
                        return arr;
                    }
                });

                // 4. 伪装 window.chrome
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {},
                };

                // 5. 伪装 permissions
                const _origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = function(parameters) {
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({state: Notification.permission, onchange: null});
                    }
                    return _origQuery(parameters);
                };

                // 6. 保证 hardwareConcurrency 不低于 4
                if (navigator.hardwareConcurrency < 4) {
                    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                }

                // 7. 伪装 deviceMemory
                if (!navigator.deviceMemory) {
                    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                }

                // 8. 覆盖 closed shadow DOM 检测
                const _origAttachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function(init) {
                    if (init && init.mode === 'closed') {
                        init.mode = 'open';
                    }
                    return _origAttachShadow.call(this, init);
                };
            """)
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
                    task.result_queue.put(self._fetch_with_page(page, task.url))
            finally:
                self._ready_event.set()
                context.close()

    def _simulate_human_behavior(self, page) -> None:  # pragma: no cover
        """模拟真人浏览行为：多段随机等待、渐进滚动、鼠标移动。"""
        try:
            # 先随机停留，模拟阅读时间
            page.wait_for_timeout(random.randint(1500, 3500))
            # 第一次向下滚动（模拟浏览）
            scroll_distance = random.randint(200, 600)
            page.mouse.wheel(0, scroll_distance)
            page.wait_for_timeout(random.randint(600, 1800))
            # 有时继续往下看
            if random.random() > 0.4:
                page.mouse.wheel(0, random.randint(100, 400))
                page.wait_for_timeout(random.randint(500, 1500))
            # 有时回滚（模拟回看）
            if random.random() > 0.55:
                page.mouse.wheel(0, -random.randint(80, 250))
                page.wait_for_timeout(random.randint(400, 1200))
            # 随机移动鼠标到页面不同区域
            page.mouse.move(random.randint(200, 900), random.randint(150, 700))
            page.wait_for_timeout(random.randint(300, 1000))
            # 有时再移动一次
            if random.random() > 0.5:
                page.mouse.move(random.randint(100, 700), random.randint(200, 550))
                page.wait_for_timeout(random.randint(200, 800))
        except Exception:
            try:
                page.wait_for_timeout(5000)
            except Exception:
                pass

    def _fetch_with_page(self, page, url: str) -> PageCapture:  # pragma: no cover - browser integration
        try:
            # 导航前先做短暂停留，降低连续跳转的机器感
            page.wait_for_timeout(random.randint(800, 2000))
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self._simulate_human_behavior(page)
            return self._capture_current_page(page)
        except Exception as exc:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            try:
                page.wait_for_timeout(3000)
            except Exception:
                pass
            return self._capture_current_page(page, error=f"页面跳转被淘宝重定向：{exc}")

    def session_keepalive(self) -> bool:
        """预刷新会话：访问淘宝首页并模拟真人浏览，重置超时计时器"""
        try:
            if not self._ready_event.is_set():
                return False
            result_queue: queue.Queue[PageCapture] = queue.Queue(maxsize=1)
            self._tasks.put(_FetchTask(url="https://www.taobao.com/", result_queue=result_queue))
            capture = result_queue.get(timeout=30.0)
            if capture.error and ("登录" in capture.error or "验证" in capture.error):
                # 可能被重定向到登录页，但仍算完成（至少触发了网络活动）
                return True
            return not capture.error
        except Exception:
            return False

    def _capture_current_page(self, page, *, error: str = "") -> PageCapture:  # pragma: no cover - browser integration
        final_url = ""
        page_title = ""
        try:
            final_url = page.url
            self._current_url = final_url
        except Exception:
            pass
        try:
            page_title = page.title()
        except Exception:
            pass
        try:
            visible_text = page.locator("body").inner_text(timeout=10000)
        except Exception as exc:
            combined_error = f"{error}\n页面文本读取失败：{exc}".strip()
            return PageCapture(final_url=final_url, page_title=page_title, error=combined_error)
        return PageCapture(visible_text=visible_text, final_url=final_url, page_title=page_title, error=error)
