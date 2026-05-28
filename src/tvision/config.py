import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    model: str = "qwen/qwen3.6-35b-a3b"
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    viewport_width: int = 1280
    viewport_height: int = 720
    headed: bool = True
    max_iters: int = 30
    wall_clock_timeout_s: int = 300
    image_history_window: int = 3
    type_delay_ms: int = 20
    settle_delay_ms: int = 250
    nav_timeout_ms: int = 15000
    trace_dir: str = field(
        default_factory=lambda: os.getenv("TVISION_TRACE_DIR", "./traces")
    )
    screenshots_dir: str = "./screenshots"
