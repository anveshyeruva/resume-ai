from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.ai_tasks import build_bullet_rewrite_prompt
from services.llm.factory import get_provider


# Matches common bullet/number prefixes:
# - bullet symbols: -, •, *
# - numbering: 1. 1) 2. 2)
# - letter bullets: a) b) A. B.
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-•*]+|\d+[.)]|\([0-9]+\)|[a-zA-Z][.)])\s+")
_HEADING_RE = re.compile(
    r"^\s*(?:rewritten|resume|bullets?|output|here are|summary|responsibilities)\s*[:\-]?\s*$",
    re.IGNORECASE,
)


def _normalize_bullets(text: str, max_items: int = 12) -> List[str]:
    """
    Convert arbitrary LLM output into clean resume bullets.
    - Removes headings
    - Accepts bullets, numbering, and wraps multi-line bullets
    - Dedupes
    """
    if not text:
        return []

    # Strip blank lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Remove obvious headings
    cleaned: List[str] = []
    for ln in lines:
        if _HEADING_RE.match(ln):
            continue
        cleaned.append(ln)

    bullets: List[str] = []
    buf: List[str] = []

    def flush_buf():
        nonlocal buf
        if not buf:
            return
        joined = " ".join(buf).strip()
        buf = []
        if joined:
            bullets.append(joined)

    for ln in cleaned:
        # New bullet start if it has a prefix
        if _BULLET_PREFIX_RE.match(ln):
            flush_buf()
            ln = _BULLET_PREFIX_RE.sub("", ln).strip()
            if ln:
                buf.append(ln)
        else:
            # Continuation line: attach to previous bullet
            if buf:
                buf.append(ln)
            else:
                # If model forgot prefixes entirely, treat as first bullet anyway
                buf.append(ln)

    flush_buf()

    # Final cleanup + dedupe
    out: List[str] = []
    seen = set()
    for b in bullets:
        b = re.sub(r"\s+", " ", b).strip()
        b = b.rstrip(" ;")
        if len(b) < 4:
            continue
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
        if len(out) >= max_items:
            break

    return out


def rewrite_responsibilities(
    responsibilities: list[str],
    *,
    jd_keywords: list[str],
    ai_mode: str,
    ollama_base_url: str,
    ollama_model: str,
    cloud_provider: str,
    openai_api_key: str,
    openai_model: str,
) -> Dict[str, Any]:
    """
    Returns:
      {"rewritten": list[str] | None, "error": str | None}
    """
    try:
        provider = get_provider(
            ai_mode,
            ollama_base_url=ollama_base_url,
            ollama_model=ollama_model,
            cloud_provider=cloud_provider,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
        )

        if provider is None:
            return {"rewritten": None, "error": None}

        items = [x.strip() for x in (responsibilities or []) if x and x.strip()]
        if not items:
            return {"rewritten": [], "error": None}

        prompt = build_bullet_rewrite_prompt(items, jd_keywords)

        raw = provider.generate(prompt)

        rewritten = _normalize_bullets(raw, max_items=12)

        # Fallback: if parsing yields nothing, return first few non-empty lines
        if not rewritten:
            rewritten = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()][:12] or None

        return {"rewritten": rewritten, "error": None}

    except Exception as e:
        return {"rewritten": None, "error": str(e)}
