import os

from openai import OpenAI


DEFAULT_BASE_URL = (
    "https://api.xiaomimimo.com/v1"
)

DEFAULT_MODEL = (
    "mimo-v2.5-pro"
)


def get_mimo_client() -> OpenAI:
    """
    Build MiMo OpenAI-compatible client.
    """

    api_key = os.getenv(
        "MIMO_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "MIMO_API_KEY is not set"
        )

    base_url = os.getenv(
        "MIMO_BASE_URL",
        DEFAULT_BASE_URL,
    )

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
    )


def get_mimo_model() -> str:
    """
    Return model name.

    Can be overridden using:
        export MIMO_MODEL=...
    """

    return os.getenv(
        "MIMO_MODEL",
        DEFAULT_MODEL,
    )
