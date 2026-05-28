"""Smoke test: open HN, click the third story, finish with its title."""

from pathlib import Path

from tvision.browser import BrowserSession
from tvision.client import make_client
from tvision.config import Settings
from tvision.loop import AgentLoop
from tvision.trace import Tracer


def main() -> int:
    settings = Settings()
    tracer = Tracer(Path(settings.trace_dir))
    client = make_client(settings)
    try:
        with BrowserSession(settings) as browser:
            loop = AgentLoop(client, browser, settings, tracer)
            result = loop.run(
                "Open https://news.ycombinator.com, click the third story link, "
                "then call finish with the story title as `result`."
            )
    finally:
        tracer.close()
    print(result)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
