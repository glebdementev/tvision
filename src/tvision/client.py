from openai import OpenAI

from .config import Settings


def make_client(settings: Settings) -> OpenAI:
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set (export it or put it in .env)"
        )
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
