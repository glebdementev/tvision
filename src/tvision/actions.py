from __future__ import annotations

import time
from typing import Any

from .browser import BrowserSession
from .config import Settings
from .keymap import normalize_modifiers, to_playwright


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture a fresh screenshot of the current page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "goto",
            "description": "Navigate to a URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at absolute pixel coordinates (0..1279 x, 0..719 y).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["ctrl", "shift", "alt", "meta"],
                        },
                    },
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double-click at absolute pixel coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "triple_click",
            "description": "Triple-click at absolute pixel coordinates (selects line/paragraph).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type",
            "description": "Type literal text at the current focus. Does not press Enter.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key",
            "description": "Press a key combo, e.g. 'Return', 'Escape', 'ctrl+a', 'shift+Tab'.",
            "parameters": {
                "type": "object",
                "properties": {"combo": {"type": "string"}},
                "required": ["combo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Wheel-scroll by dy pixels at (x,y). Positive dy scrolls down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "dy": {"type": "integer"},
                },
                "required": ["x", "y", "dy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "Mouse-drag from (x1,y1) to (x2,y2) with the left button.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"},
                    "y1": {"type": "integer"},
                    "x2": {"type": "integer"},
                    "y2": {"type": "integer"},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Sleep for `seconds` (capped at 10).",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "number"}},
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Terminate the loop. Call with success=true and a result summary when the task is "
                "complete, or success=false and a reason if it cannot be completed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "result": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["success", "result"],
            },
        },
    },
]


class Executor:
    def __init__(self, browser: BrowserSession, settings: Settings):
        self.browser = browser
        self.settings = settings

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        method = getattr(self, f"_op_{name}", None)
        if method is None:
            return f"error: unknown tool {name!r}"
        try:
            return method(**args)
        except TypeError as e:
            return f"error: bad arguments for {name}: {e}"
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    def _settle(self) -> None:
        try:
            self.browser.page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        time.sleep(self.settings.settle_delay_ms / 1000)

    def _op_screenshot(self) -> str:
        return "screenshot requested"

    def _op_goto(self, url: str) -> str:
        self.browser.page.goto(url)
        self._settle()
        return f"navigated to {url}"

    def _op_click(
        self,
        x: int,
        y: int,
        button: str = "left",
        modifiers: list[str] | None = None,
    ) -> str:
        mods = normalize_modifiers(modifiers)
        self.browser.page.mouse.click(x, y, button=button, modifiers=mods)
        self.browser.cursor = (x, y)
        self._settle()
        return f"{button} clicked at ({x},{y})"

    def _op_double_click(self, x: int, y: int) -> str:
        self.browser.page.mouse.dblclick(x, y)
        self.browser.cursor = (x, y)
        self._settle()
        return f"double-clicked at ({x},{y})"

    def _op_triple_click(self, x: int, y: int) -> str:
        self.browser.page.mouse.click(x, y, click_count=3)
        self.browser.cursor = (x, y)
        self._settle()
        return f"triple-clicked at ({x},{y})"

    def _op_type(self, text: str) -> str:
        self.browser.page.keyboard.type(text, delay=self.settings.type_delay_ms)
        return f"typed {len(text)} chars"

    def _op_key(self, combo: str) -> str:
        self.browser.page.keyboard.press(to_playwright(combo))
        self._settle()
        return f"pressed {combo}"

    def _op_scroll(self, x: int, y: int, dy: int) -> str:
        self.browser.page.mouse.move(x, y)
        self.browser.page.mouse.wheel(0, dy)
        time.sleep(self.settings.settle_delay_ms / 1000)
        return f"scrolled dy={dy} at ({x},{y})"

    def _op_drag(self, x1: int, y1: int, x2: int, y2: int) -> str:
        m = self.browser.page.mouse
        m.move(x1, y1)
        m.down()
        m.move(x2, y2)
        m.up()
        self.browser.cursor = (x2, y2)
        self._settle()
        return f"dragged ({x1},{y1}) -> ({x2},{y2})"

    def _op_wait(self, seconds: float) -> str:
        capped = min(float(seconds), 10.0)
        time.sleep(capped)
        return f"waited {capped}s"
