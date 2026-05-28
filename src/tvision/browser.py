from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .config import Settings


class BrowserSession:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.cursor: tuple[int, int] = (0, 0)

    def start(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=not self.settings.headed)
        self._context = self._browser.new_context(
            viewport={
                "width": self.settings.viewport_width,
                "height": self.settings.viewport_height,
            },
            device_scale_factor=1,
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.settings.nav_timeout_ms)

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserSession.start() was not called")
        return self._page

    def screenshot(self) -> bytes:
        return self.page.screenshot(type="png", full_page=False)

    def stop(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
