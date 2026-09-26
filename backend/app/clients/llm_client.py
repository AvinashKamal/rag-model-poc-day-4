import threading

import httpx
from openai import OpenAI

from app.config import settings

# This is OpenRouter, not Anthropic directly: the only LLM key available is an
# OpenRouter key, so generation goes through the OpenAI-compatible client
# pointed at OpenRouter's base URL. The app never calls the Anthropic SDK.

# The SDK's own unset-timeout default is httpx.Timeout(connect=5.0, read=600,
# write=600, pool=600) — nobody chose that, it's just what's left over from
# a general-purpose client default. /query sends a synthesis prompt built
# from up to `top_k` (<=50) reranked abstracts, so prompt size varies a lot
# call to call; connect stays at the SDK's own 5s (OpenRouter is a public
# HTTPS endpoint, not a same-network service, so 5s to establish a
# connection is already generous). Read/write/pool are pulled down to 60s:
# generous headroom above a normal single-turn completion at this prompt
# size, while still failing fast enough that a genuinely stuck OpenRouter
# call surfaces as an UpstreamServiceError (see errors.py) well inside a
# typical HTTP client's own request timeout, instead of hanging for 10
# minutes on the library default.
_LLM_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0)

_client: OpenAI | None = None
_client_lock = threading.Lock()


def get_llm_client() -> OpenAI:
    """Process-wide singleton OpenAI client (pointed at OpenRouter) so
    repeated /query calls reuse one connection pool instead of constructing a
    fresh client — and a fresh underlying httpx connection — every call.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(
                    base_url=settings.OPENROUTER_BASE_URL,
                    api_key=settings.OPENROUTER_API_KEY,
                    timeout=_LLM_TIMEOUT,
                )
    return _client
