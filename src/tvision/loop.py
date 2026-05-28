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
from .screenshot import data_url_png, png_size
from .trace import Tracer


EMPTY_NUDGE = (
    "Your previous response produced no tool call (likely you stopped after "
    "internal reasoning). You MUST emit exactly one tool call now. Pick the "
    "next action and call `computer_use` with the appropriate `action` "
    "field, or call `finish` if the task is complete. Do not produce only "
    "text — emit the tool call."
)

MAX_ATTEMPTS_PER_STEP = 3


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


def _sanitize_for_dump(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        copy = dict(m)
        content = copy.get("content")
        if isinstance(content, list):
            new_content: list[dict] = []
            for part in content:
                if not isinstance(part, dict):
                    new_content.append(part)
                    continue
                if part.get("type") == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    new_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"[data URI omitted: {len(url)} chars]"
                            },
                        }
                    )
                else:
                    new_content.append(part)
            copy["content"] = new_content
        out.append(copy)
    return out


def _response_to_dict(resp: Any) -> Any:
    try:
        return resp.model_dump()
    except Exception:
        try:
            return json.loads(resp.model_dump_json())
        except Exception:
            return {"repr": repr(resp)}


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

    def _call_model(
        self, messages: list[dict], *, force_tool: bool
    ) -> Any:
        return self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="required" if force_tool else "auto",
        )

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
        shot_path = self.tracer.record_screenshot(0, img)
        _log(
            f"[tvision] step 0 initial screenshot: {sz[0]}x{sz[1]} "
            f"({len(img)} bytes) → {shot_path}"
        )
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

            msg, tool_calls = self._sample_with_retry(step, messages)

            if not tool_calls:
                _log(
                    f"[tvision] step {step}: ✗ no tool call after "
                    f"{MAX_ATTEMPTS_PER_STEP} attempts — giving up"
                )
                self.tracer.record_finish(
                    step, False, "", "no tool call after retries"
                )
                return FinishResult(
                    False, "", "no tool call after retries", step
                )

            messages.append(_assistant_to_dict(msg))

            should_continue = self._process_tool_calls(step, tool_calls, messages)
            if isinstance(should_continue, FinishResult):
                return should_continue

            img = self.browser.screenshot()
            sz = png_size(img) or (-1, -1)
            shot_path = self.tracer.record_screenshot(step, img)
            _log(
                f"[tvision] step {step}: post-action screenshot: "
                f"{sz[0]}x{sz[1]} ({len(img)} bytes) → {shot_path}"
            )
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

    def _sample_with_retry(
        self, step: int, messages: list[dict]
    ) -> tuple[Any, list[Any]]:
        """Call the model up to MAX_ATTEMPTS_PER_STEP times, adding a nudge
        and escalating to tool_choice='required' if the response has no
        tool_calls. Empty assistant turns are NOT stored in history (only
        the final usable response is). Nudges ARE stored so subsequent
        attempts see the prior instruction."""
        msg: Any = None
        tool_calls: list[Any] = []
        nudged = False

        for attempt in range(MAX_ATTEMPTS_PER_STEP):
            tag = f"{step:03d}-a{attempt}"
            force_tool = attempt > 0
            choice_str = "required" if force_tool else "auto"

            req_path = self.tracer.dump_request(tag, _sanitize_for_dump(messages))
            _log(
                f"[tvision] step {step} attempt {attempt}: "
                f"→ POST /chat/completions msgs={len(messages)} "
                f"tool_choice={choice_str} (dump: {req_path.name})"
            )
            t0 = time.monotonic()
            try:
                resp = self._call_model(messages, force_tool=force_tool)
            except Exception as e:
                _log(
                    f"[tvision] step {step} attempt {attempt}: "
                    f"✗ API error: {type(e).__name__}: {e}"
                )
                raise
            dt = time.monotonic() - t0

            resp_path = self.tracer.dump_response(tag, _response_to_dict(resp))

            choice = resp.choices[0]
            msg = choice.message
            tool_calls = list(msg.tool_calls or [])
            usage = getattr(resp, "usage", None)
            usage_str = ""
            if usage:
                comp = getattr(usage, "completion_tokens", "?")
                prom = getattr(usage, "prompt_tokens", "?")
                reas = None
                ctd = getattr(usage, "completion_tokens_details", None)
                if ctd is not None:
                    reas = getattr(ctd, "reasoning_tokens", None)
                usage_str = f" tokens={prom}+{comp}"
                if reas:
                    usage_str += f" (reasoning={reas})"
            _log(
                f"[tvision] step {step} attempt {attempt}: ← {dt:.2f}s "
                f"finish={choice.finish_reason} tool_calls={len(tool_calls)}"
                f"{usage_str} (dump: {resp_path.name})"
            )

            self.tracer.record_assistant(
                step,
                msg.content,
                [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in tool_calls
                ],
            )

            if msg.content:
                _log(f"[tvision] step {step} attempt {attempt}:   text: {_preview(msg.content)}")

            if tool_calls:
                return msg, tool_calls

            # Empty (or text-only) response — surface details and retry.
            if msg.content:
                _log(f"[tvision] step {step} attempt {attempt}:   (text-only, no tool call)")
                for line in (msg.content or "").splitlines() or [""]:
                    _log(f"[tvision]      | {line}")
            else:
                _log(f"[tvision] step {step} attempt {attempt}:   (empty response — likely swallowed by reasoning)")

            if attempt < MAX_ATTEMPTS_PER_STEP - 1:
                if not nudged:
                    _log(
                        f"[tvision] step {step} attempt {attempt}: "
                        f"adding nudge and escalating tool_choice=required"
                    )
                    messages.append({"role": "user", "content": EMPTY_NUDGE})
                    nudged = True
                else:
                    _log(
                        f"[tvision] step {step} attempt {attempt}: "
                        f"retrying with tool_choice=required"
                    )

        return msg, tool_calls

    def _process_tool_calls(
        self, step: int, tool_calls: list[Any], messages: list[dict]
    ) -> FinishResult | None:
        """Execute each tool call, append tool results to messages. Return
        a FinishResult if `finish` was invoked, else None to continue."""
        for call in tool_calls:
            name = call.function.name
            raw_args = call.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            _log(
                f"[tvision] step {step}:   → {name}({_preview(raw_args, 240)})"
            )

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
        return None

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
    """Serialize an assistant message for replay. Omits the `reasoning`
    field intentionally — we never replay the model's internal thinking
    back to it (matches sop-agent's behavior, and prevents reasoning
    models from doubling-down on prior empty turns)."""
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
