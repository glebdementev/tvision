from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class Tracer:
    def __init__(self, root: str | Path):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = Path(root) / ts
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = (self.dir / "trace.jsonl").open("a")

    def _write(self, event: dict[str, Any]) -> None:
        event["ts"] = time.time()
        self.log.write(json.dumps(event) + "\n")
        self.log.flush()

    def record_task(self, task: str, model: str) -> None:
        self._write({"event": "task", "task": task, "model": model})

    def record_screenshot(self, step: int, png: bytes) -> None:
        name = f"step-{step:03d}.png"
        (self.dir / name).write_bytes(png)
        self._write({"event": "screenshot", "step": step, "path": name})

    def record_assistant(self, step: int, content: str | None, tool_calls: list[dict]) -> None:
        self._write(
            {
                "event": "assistant",
                "step": step,
                "content": content,
                "tool_calls": tool_calls,
            }
        )

    def record_tool(self, step: int, name: str, args: dict, status: str) -> None:
        self._write(
            {
                "event": "tool",
                "step": step,
                "name": name,
                "args": args,
                "status": status,
            }
        )

    def record_finish(self, step: int, success: bool, result: str, reason: str | None) -> None:
        self._write(
            {
                "event": "finish",
                "step": step,
                "success": success,
                "result": result,
                "reason": reason,
            }
        )

    def close(self) -> None:
        self.log.close()
