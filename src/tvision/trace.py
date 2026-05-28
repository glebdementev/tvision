from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class Tracer:
    def __init__(self, trace_root: str | Path, screenshots_root: str | Path):
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = Path(trace_root) / self.run_id
        self.screenshots_dir = Path(screenshots_root) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.log = (self.dir / "trace.jsonl").open("a")

    def _write(self, event: dict[str, Any]) -> None:
        event["ts"] = time.time()
        self.log.write(json.dumps(event, default=str) + "\n")
        self.log.flush()

    def _write_json(self, name: str, obj: Any) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(obj, indent=2, default=str))
        return path

    def record_task(self, task: str, model: str) -> None:
        self._write({"event": "task", "task": task, "model": model})

    def record_screenshot(self, step: int, png: bytes) -> Path:
        name = f"step-{step:03d}.png"
        path = self.screenshots_dir / name
        path.write_bytes(png)
        self._write(
            {
                "event": "screenshot",
                "step": step,
                "path": str(path),
                "bytes": len(png),
            }
        )
        return path

    def record_assistant(
        self,
        step: int,
        content: str | None,
        tool_calls: list[dict],
    ) -> Path | None:
        self._write(
            {
                "event": "assistant",
                "step": step,
                "content": content,
                "tool_calls": tool_calls,
            }
        )
        if content:
            path = self.dir / f"step-{step:03d}-assistant.txt"
            path.write_text(content)
            return path
        return None

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

    def record_finish(
        self, step: int, success: bool, result: str, reason: str | None
    ) -> None:
        self._write(
            {
                "event": "finish",
                "step": step,
                "success": success,
                "result": result,
                "reason": reason,
            }
        )

    def dump_request(self, step: int, payload: Any) -> Path:
        return self._write_json(f"step-{step:03d}-request.json", payload)

    def dump_response(self, step: int, payload: Any) -> Path:
        return self._write_json(f"step-{step:03d}-response.json", payload)

    def close(self) -> None:
        self.log.close()
