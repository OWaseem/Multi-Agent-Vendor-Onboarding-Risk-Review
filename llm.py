"""Model-agnostic LLM client.

Reads provider configuration from ``.env`` via python-dotenv. Preference order:

1. Amazon Bedrock (``BEDROCK_MODEL_ID``, credentials via the standard AWS
   chain: ``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY``/``AWS_REGION``,
   ``AWS_PROFILE``, or ``~/.aws/credentials``)
2. OpenAI (``OPENAI_API_KEY``)
3. Anthropic (``ANTHROPIC_API_KEY``)

When none is configured, ``get_llm()`` returns ``None`` and the
planner/reviewer nodes fall back to deterministic template prose, so the whole
pipeline runs offline.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv()

#: Default Bedrock model id; override with BEDROCK_MODEL_ID in .env.
DEFAULT_BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def _bedrock_configured() -> bool:
    aws_creds = {
        "BEDROCK_MODEL_ID",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
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
    return None


@lru_cache(maxsize=1)
def get_llm() -> Any | None:
    """Return the configured LLM client, or None when no provider is set."""
    return _llm()


def llm_text(prompt: str, max_tokens: int = 200) -> str | None:
    """Run a single prompt; return text, or None when no LLM is configured."""
    llm = get_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return str(content).strip()
    except Exception as exc:  # pragma: no cover - network/provider errors
        return None
