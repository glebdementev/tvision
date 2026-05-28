import os
from dataclasses import dataclass


@dataclass
class Settings:
    model: str = os.getenv("TVISION_MODEL", "qwen/qwen3-vl-plus")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )
    viewport_width: int = 1280
    viewport_height: int = 720
    headed: bool = True
    max_iters: int = 30
    wall_clock_timeout_s: int = 300
    image_history_window: int = 3
    type_delay_ms: int = 20
    settle_delay_ms: int = 250
    nav_timeout_ms: int = 15000
    trace_dir: str = os.getenv("TVISION_TRACE_DIR", "./traces")
