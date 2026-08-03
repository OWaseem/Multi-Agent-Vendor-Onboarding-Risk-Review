"""Model-agnostic LLM client.

Reads provider configuration from ``.env`` via python-dotenv. Preference order:

1. Amazon Bedrock (``BEDROCK_MODEL_ID``, credentials via the standard AWS
   chain: ``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY``/``AWS_REGION``,
   ``AWS_PROFILE``, or a Bedrock API key in ``AWS_BEARER_TOKEN_BEDROCK``)
2. OpenAI (``OPENAI_API_KEY``)
3. Anthropic (``ANTHROPIC_API_KEY``)
4. Google Gemini (``GOOGLE_API_KEY``)

When none is configured, ``get_llm()`` returns ``None`` and the
planner/reviewer nodes fall back to deterministic template prose, so the whole
pipeline runs offline.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMCallError(RuntimeError):
    """A provider *is* configured but the call itself failed (bad credentials,
    network error, wrong model id, etc.) — distinct from "no provider set",
    which is a supported, silent offline mode."""

#: Default Bedrock model id; override with BEDROCK_MODEL_ID in .env.
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-6"


def _bedrock_configured() -> bool:
    # Only actual credential sources count; BEDROCK_MODEL_ID/AWS_REGION are
    # just descriptive defaults in .env.example and must not trigger a doomed
    # Bedrock call when no credentials are actually present.
    aws_creds = {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "AWS_BEARER_TOKEN_BEDROCK",
    }
    return any(os.getenv(k) for k in aws_creds)


def _llm() -> Any | None:
    if _bedrock_configured():
        try:
            from langchain_aws import ChatBedrockConverse

            return ChatBedrockConverse(
                model_id=os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL),
                temperature=0,
                max_tokens=2048,
                region_name=os.getenv(
                    "AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")
                ),
            )
        except Exception:  # pragma: no cover - missing/misconfigured AWS SDK
            return None
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            timeout=30,
        )
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            temperature=0,
            timeout=30,
        )
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=0,
            max_output_tokens=2048,
            timeout=30,
        )
    return None


@lru_cache(maxsize=1)
def get_llm() -> Any | None:
    """Return the configured LLM client, or None when no provider is set."""
    return _llm()


def llm_text(prompt: str, max_tokens: int = 200) -> str | None:
    """Run a single prompt; return text, or None when no LLM is configured.

    Raises ``LLMCallError`` when a provider *is* configured but the call
    itself fails — callers should catch this, fall back to template text, and
    surface the failure rather than silently swallowing it.
    """
    llm = get_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return str(content).strip()
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise LLMCallError(str(exc)) from exc
