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
        w = self.settings.viewport_width
        h = self.settings.viewport_height
        # Window height = viewport + ~100px chrome (URL bar, tabs).
        self._browser = self._pw.chromium.launch(
            headless=not self.settings.headed,
            args=[
                f"--window-size={w},{h + 100}",
                "--window-position=0,0",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": w, "height": h},
            screen={"width": w, "height": h},
            device_scale_factor=1,
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.settings.nav_timeout_ms)
        if self.settings.start_url:
            self._page.goto(self.settings.start_url)
            try:
                self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

    def actual_viewport(self) -> tuple[int, int]:
        size = self.page.evaluate("() => [window.innerWidth, window.innerHeight]")
        return int(size[0]), int(size[1])

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
