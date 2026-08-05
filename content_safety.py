"""Deterministic content-safety screening for free-text request fields.

Screens ``vendor_name`` and ``business_justification`` for two things:

1. Unsafe content — threats, violence, weapons — which must never be silently
   approved.
2. Disclosed security incidents — mentions of a past breach/hack/compromise —
   which is a legitimate additional risk signal, not a safety issue.

This keyword scan is a deterministic baseline that always runs, regardless of
whether an LLM provider is configured (mirrors the rest of the project's
"deterministic core, LLM adds nuance" design). See
``graph.nodes.content_safety_check`` for how it's combined with an optional
LLM classification pass.
"""

from __future__ import annotations

import re

UNSAFE_CONTENT_PATTERNS = [
    r"\bkill(ing)?\b",
    r"\bbomb(ing)?\b",
    r"\bshoot(ing)?\b",
    r"\bweapon(s|ize[d]?)?\b",
    r"\bterroris[mt]\b",
    r"\bthreat(en|ening|ened)?\b",
    r"\battack(ing)?\b",
    r"\bmurder(ed|ing)?\b",
    r"\bhostage\b",
    r"\bassault(ed|ing)?\b",
    r"\bhurt (you|him|her|them)\b",
]

SECURITY_INCIDENT_PATTERNS = [
    r"\bdata breach\b",
    r"\bbreach(ed)?\b",
    r"\bhack(ed|ing)?\b",
    r"\bransomware\b",
    r"\bcompromise[d]?\b",
    r"\bleak(ed)?\b",
    r"\bunauthorized access\b",
    r"\bsecurity incident\b",
    r"\bexploit(ed)?\b",
]


def _matches(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [p for p in patterns if re.search(p, lowered)]


def scan_unsafe_content(text: str) -> list[str]:
    """Return the matched patterns indicating threats/violence, or []."""
    return _matches(text, UNSAFE_CONTENT_PATTERNS)


def scan_security_incident(text: str) -> list[str]:
    """Return the matched patterns indicating a disclosed security incident, or []."""
    return _matches(text, SECURITY_INCIDENT_PATTERNS)
