from __future__ import annotations

import re
from typing import Any, Dict, List

from core.ai_tasks import build_bullet_rewrite_prompt
from services.llm.factory import get_provider

_BULLET_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+(.*)\s*$")

def _extract_bullets(text: str, max_items: int = 20) -> List[str]:
    out: List[str] = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = _BULLET_RE.match(ln)
        if not m:
            continue
        item = (m.group(1) or "").strip()
        if len(item) < 4:
            continue
        out.append(item)
        if len(out) >= max_items:
            break

    seen = set()
    deduped: List[str] = []
    for b in out:
        k = b.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(b)
    return deduped

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

        prompt = build_bullet_rewrite_prompt(responsibilities, jd_keywords)
        out = provider.generate(prompt)

        rewritten = _extract_bullets(out)
        if not rewritten:
            rewritten = [ln.strip() for ln in out.splitlines() if ln.strip()][:12] or None

        return {"rewritten": rewritten, "error": None}
    except Exception as e:
        return {"rewritten": None, "error": str(e)}
