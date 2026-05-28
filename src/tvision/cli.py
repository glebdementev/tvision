from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .browser import BrowserSession
from .client import make_client
from .config import Settings
from .loop import AgentLoop
from .trace import Tracer


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(
        prog="tvision",
        description="Vision-driven browser agent (Qwen 3.6 + Playwright, 1280x720)",
    )
    parser.add_argument("task", help="Natural-language task for the agent")
    parser.add_argument("--model", default=None, help="Override model slug")
    parser.add_argument("--max-iters", type=int, default=None)
    parser.add_argument("--headless", action="store_true", help="Run Chromium headless")
    parser.add_argument("--trace-dir", default=None)
    args = parser.parse_args(argv)

    settings = Settings()
    if args.model:
        settings.model = args.model
    if args.max_iters is not None:
        settings.max_iters = args.max_iters
    if args.headless:
        settings.headed = False
    if args.trace_dir:
        settings.trace_dir = args.trace_dir

    tracer = Tracer(settings.trace_dir)
    client = make_client(settings)
    print(f"[tvision] trace dir: {tracer.dir}", flush=True)

    try:
        with BrowserSession(settings) as browser:
            actual = browser.actual_viewport()
            print(
                f"[tvision] browser ready: viewport reports {actual[0]}x{actual[1]}"
                f" (configured {settings.viewport_width}x{settings.viewport_height},"
                f" headed={settings.headed})",
                flush=True,
            )
            loop = AgentLoop(client, browser, settings, tracer)
            result = loop.run(args.task)
    finally:
        tracer.close()

    print(f"\nsuccess={result.success} steps={result.steps}")
    if result.result:
        print(f"result: {result.result}")
    if result.reason:
        print(f"reason: {result.reason}")
    print(f"trace: {tracer.dir}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
