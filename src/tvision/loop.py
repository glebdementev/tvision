from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .actions import TOOL_SCHEMAS, Executor
from .browser import BrowserSession
from .config import Settings
from .prompts import SYSTEM
from .screenshot import data_url_png, png_size
from .trace import Tracer


@dataclass
class FinishResult:
    success: bool
    result: str
    reason: str | None = None
    steps: int = 0


def _log(msg: str) -> None:
    print(msg, flush=True)


def _preview(s: str | None, n: int = 200) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


class AgentLoop:
    def __init__(
        self,
        client: OpenAI,
        browser: BrowserSession,
        settings: Settings,
        tracer: Tracer,
    ):
        self.client = client
        self.browser = browser
        self.settings = settings
        self.tracer = tracer
        self.executor = Executor(browser, settings)

    def run(self, task: str) -> FinishResult:
        _log(
            f"[tvision] model={self.settings.model} "
            f"viewport={self.settings.viewport_width}x{self.settings.viewport_height} "
            f"max_iters={self.settings.max_iters}"
        )
        _log(f"[tvision] task: {task}")
        self.tracer.record_task(task, self.settings.model)

        messages: list[dict] = [{"role": "system", "content": SYSTEM}]
        img = self.browser.screenshot()
        sz = png_size(img) or (-1, -1)
        _log(
            f"[tvision] step 0 initial screenshot: {sz[0]}x{sz[1]} "
            f"({len(img)} bytes)"
        )
        self.tracer.record_screenshot(0, img)
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Task: {task}"},
                    {"type": "image_url", "image_url": {"url": data_url_png(img)}},
                ],
            }
        )

        start = time.monotonic()

        for step in range(1, self.settings.max_iters + 1):
            if time.monotonic() - start > self.settings.wall_clock_timeout_s:
                _log(f"[tvision] step {step}: wall clock timeout")
                self.tracer.record_finish(step, False, "", "wall clock timeout")
                return FinishResult(False, "", "wall clock timeout", step)

            self._prune_images(messages)

            _log(
                f"[tvision] step {step}: → POST /chat/completions "
                f"msgs={len(messages)}"
            )
            t0 = time.monotonic()
            try:
                resp = self.client.chat.completions.create(
                    model=self.settings.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                )
            except Exception as e:
                _log(f"[tvision] step {step}: ✗ API error: {type(e).__name__}: {e}")
                raise
            dt = time.monotonic() - t0

            choice = resp.choices[0]
            msg = choice.message
            tool_calls = list(msg.tool_calls or [])
            usage = getattr(resp, "usage", None)
            usage_str = (
                f" tokens={usage.prompt_tokens}+{usage.completion_tokens}"
                if usage
                else ""
            )
            _log(
                f"[tvision] step {step}: ← {dt:.2f}s "
                f"finish={choice.finish_reason} tool_calls={len(tool_calls)}"
                f"{usage_str}"
            )
            if msg.content:
                _log(f"[tvision] step {step}:   text: {_preview(msg.content)}")

            self.tracer.record_assistant(
                step,
                msg.content,
                [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in tool_calls
                ],
            )

            messages.append(_assistant_to_dict(msg))

            if not tool_calls:
                _log(
                    f"[tvision] step {step}: no tool call — nudging model to use a tool"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Please call exactly one tool. If the task is complete, "
                            "call `finish`."
                        ),
                    }
                )
                continue

            for call in tool_calls:
                name = call.function.name
                raw_args = call.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
                _log(f"[tvision] step {step}:   → {name}({_preview(raw_args, 240)})")

                if name == "finish":
                    success = bool(args.get("success", False))
                    result_text = str(args.get("result", ""))
                    reason = args.get("reason")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": "finished",
                        }
                    )
                    _log(
                        f"[tvision] step {step}:   ← finish "
                        f"success={success} result={_preview(result_text)}"
                    )
                    self.tracer.record_finish(step, success, result_text, reason)
                    return FinishResult(success, result_text, reason, step)

                status = self.executor.dispatch(name, args)
                _log(f"[tvision] step {step}:   ← {status}")
                self.tracer.record_tool(step, name, args, status)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": status,
                    }
                )

            img = self.browser.screenshot()
            sz = png_size(img) or (-1, -1)
            _log(
                f"[tvision] step {step}: post-action screenshot: "
                f"{sz[0]}x{sz[1]} ({len(img)} bytes)"
            )
            self.tracer.record_screenshot(step, img)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url_png(img)}},
                    ],
                }
            )

        _log(f"[tvision] max iters ({self.settings.max_iters}) reached")
        self.tracer.record_finish(
            self.settings.max_iters, False, "", "max iters reached"
        )
        return FinishResult(False, "", "max iters reached", self.settings.max_iters)

    def _prune_images(self, messages: list[dict]) -> None:
        window = self.settings.image_history_window
        idxs = [
            i
            for i, m in enumerate(messages)
            if m.get("role") == "user" and isinstance(m.get("content"), list)
        ]
        if len(idxs) <= window:
            return
        for i in idxs[:-window]:
            new_content: list[dict] = []
            for part in messages[i]["content"]:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    new_content.append({"type": "text", "text": "[screenshot omitted]"})
                else:
                    new_content.append(part)
            messages[i]["content"] = new_content


def _assistant_to_dict(msg: Any) -> dict:
    out: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return out
