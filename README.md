# tvision

Vision-driven browser agent. Drives headed Chromium at 1280x720 using `qwen/qwen3.6-35b-a3b` via OpenRouter.

## Quickstart

```bash
pip install -e .
playwright install chromium
cp .env.example .env  # paste your OPENROUTER_API_KEY
tvision "open https://news.ycombinator.com, click the third story, then finish with its title"
```

Per-step JSONL + PNG traces land in `./traces/<run-id>/`.

## Layout

- `src/tvision/loop.py` — sync agent loop
- `src/tvision/browser.py` — Playwright sync session, 1280x720, DSF=1, fresh context per run
- `src/tvision/actions.py` — tool schemas + executor
- `src/tvision/trace.py` — per-step JSONL + PNG dump

Coordinates are absolute pixels (0..1279, 0..719), passed straight to Playwright.
