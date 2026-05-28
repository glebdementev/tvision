from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from .keymap import to_playwright

if TYPE_CHECKING:
    from .browser import BrowserSession
    from .config import Settings


VIRTUAL_RES = 1000

COMPUTER_USE_ACTIONS = [
    "screenshot",
    "goto",
    "mouse_move",
    "left_click",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "left_click_drag",
    "type",
    "key",
    "scroll",
    "wait",
]


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "computer_use",
            "description": (
                "Control a Chromium browser. The actual viewport is 1280x720 px, "
                "but you MUST output coordinates in a normalized integer space "
                "[0, 999] on both axes; the runtime rescales them to real pixels "
                "before executing. (0,0) is the top-left, (999,999) the bottom-right. "
                "Call one action per turn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": COMPUTER_USE_ACTIONS,
                        "description": "Which operation to perform.",
                    },
                    "coordinate": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "[x, y] in 0..999 normalized space. Required for "
                            "mouse_move, *_click, scroll, and the start of "
                            "left_click_drag."
                        ),
                    },
                    "coordinate2": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "Drag endpoint [x, y] in 0..999 normalized space. "
                            "Used only with left_click_drag."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "For `type`: the literal text to type. "
                            "For `key`: the key or combo to press, e.g. 'Return', "
                            "'Escape', 'ctrl+a'."
                        ),
                    },
                    "url": {
                        "type": "string",
                        "description": "Destination URL for `goto`.",
                    },
                    "seconds": {
                        "type": "number",
                        "description": "Sleep duration for `wait`, capped at 10.",
                    },
                    "scroll_direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "Direction for `scroll`.",
                    },
                    "scroll_amount": {
                        "type": "integer",
                        "description": "Wheel-click count for `scroll` (default 3).",
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": (
                            "Override mouse button for clicks (rarely needed; use "
                            "the dedicated *_click actions instead)."
                        ),
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["ctrl", "shift", "alt", "meta"],
                        },
                        "description": "Modifier keys held during a click.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "Terminate the loop. Call with success=true and a result summary "
                "when the task is complete, or success=false and a reason if it "
                "cannot be completed."
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
        if name != "computer_use":
            return f"error: unknown tool {name!r} (expected 'computer_use' or 'finish')"
        action = args.get("action")
        if not action:
            return "error: missing 'action' field"
        method = getattr(self, f"_op_{action}", None)
        if method is None:
            return f"error: unknown action {action!r}"
        try:
            return method(args)
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    def _rescale(self, coord: Any) -> tuple[int, int]:
        if not isinstance(coord, (list, tuple)) or len(coord) != 2:
            raise ValueError("coordinate must be [x, y]")
        x, y = coord
        rx = round(float(x) / VIRTUAL_RES * self.settings.viewport_width)
        ry = round(float(y) / VIRTUAL_RES * self.settings.viewport_height)
        rx = max(0, min(self.settings.viewport_width - 1, rx))
        ry = max(0, min(self.settings.viewport_height - 1, ry))
        return rx, ry

    def _settle(self) -> None:
        try:
            self.browser.page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        time.sleep(self.settings.settle_delay_ms / 1000)

    def _op_screenshot(self, args: dict) -> str:
        return "screenshot requested"

    def _op_goto(self, args: dict) -> str:
        url = args.get("url")
        if not url:
            return "error: 'goto' requires url"
        self.browser.page.goto(url)
        self._settle()
        return f"navigated to {url}"

    def _op_mouse_move(self, args: dict) -> str:
        x, y = self._rescale(args.get("coordinate"))
        self.browser.page.mouse.move(x, y)
        self.browser.cursor = (x, y)
        return f"moved to ({x},{y})"

    def _click(self, args: dict, button: str, count: int) -> str:
        coord = args.get("coordinate")
        if coord is not None:
            x, y = self._rescale(coord)
        else:
            x, y = self.browser.cursor
        button = args.get("button", button)
        self.browser.page.mouse.click(x, y, button=button, click_count=count)
        self.browser.cursor = (x, y)
        self._settle()
        return f"{button} click x{count} at ({x},{y})"

    def _op_left_click(self, args: dict) -> str:
        return self._click(args, "left", 1)

    def _op_right_click(self, args: dict) -> str:
        return self._click(args, "right", 1)

    def _op_middle_click(self, args: dict) -> str:
        return self._click(args, "middle", 1)

    def _op_double_click(self, args: dict) -> str:
        return self._click(args, "left", 2)

    def _op_triple_click(self, args: dict) -> str:
        return self._click(args, "left", 3)

    def _op_left_click_drag(self, args: dict) -> str:
        c1 = args.get("coordinate")
        c2 = args.get("coordinate2")
        if c1 is None or c2 is None:
            return "error: 'left_click_drag' requires coordinate and coordinate2"
        x1, y1 = self._rescale(c1)
        x2, y2 = self._rescale(c2)
        m = self.browser.page.mouse
        m.move(x1, y1)
        m.down()
        m.move(x2, y2)
        m.up()
        self.browser.cursor = (x2, y2)
        self._settle()
        return f"dragged ({x1},{y1}) -> ({x2},{y2})"

    def _op_type(self, args: dict) -> str:
        text = args.get("text", "")
        self.browser.page.keyboard.type(text, delay=self.settings.type_delay_ms)
        return f"typed {len(text)} chars"

    def _op_key(self, args: dict) -> str:
        combo = args.get("text", "")
        if not combo:
            return "error: 'key' requires text (e.g. 'Return', 'ctrl+a')"
        self.browser.page.keyboard.press(to_playwright(combo))
        self._settle()
        return f"pressed {combo}"

    def _op_scroll(self, args: dict) -> str:
        coord = args.get("coordinate")
        if coord is not None:
            x, y = self._rescale(coord)
            self.browser.page.mouse.move(x, y)
        direction = args.get("scroll_direction", "down")
        amount = int(args.get("scroll_amount", 3))
        per_click = 100
        dx, dy = 0, 0
        if direction == "down":
            dy = amount * per_click
        elif direction == "up":
            dy = -amount * per_click
        elif direction == "right":
            dx = amount * per_click
        elif direction == "left":
            dx = -amount * per_click
        else:
            return f"error: bad scroll_direction {direction!r}"
        self.browser.page.mouse.wheel(dx, dy)
        time.sleep(self.settings.settle_delay_ms / 1000)
        return f"scrolled {direction} x{amount}"

    def _op_wait(self, args: dict) -> str:
        seconds = float(args.get("seconds", 1))
        capped = min(seconds, 10.0)
        time.sleep(capped)
        return f"waited {capped}s"
