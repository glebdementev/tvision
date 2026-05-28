from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .actions import TOOL_SCHEMAS, Executor
from .browser import BrowserSession
from .config import Settings
from .prompts import SYSTEM
from .screenshot import data_url_png
from .trace import Tracer


@dataclass
class FinishResult:
    success: bool
    result: str
    reason: str | None = None
    steps: int = 0


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
        self.tracer.record_task(task, self.settings.model)

        messages: list[dict] = [{"role": "system", "content": SYSTEM}]
        img = self.browser.screenshot()
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
                self.tracer.record_finish(step, False, "", "wall clock timeout")
                return FinishResult(False, "", "wall clock timeout", step)

            self._prune_images(messages)

            resp = self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            tool_calls = list(msg.tool_calls or [])

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
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

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
                    self.tracer.record_finish(step, success, result_text, reason)
                    return FinishResult(success, result_text, reason, step)

                status = self.executor.dispatch(name, args)
                self.tracer.record_tool(step, name, args, status)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": status,
                    }
                )

            img = self.browser.screenshot()
            self.tracer.record_screenshot(step, img)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url_png(img)}},
                    ],
                }
            )

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
