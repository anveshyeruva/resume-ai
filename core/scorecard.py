from __future__ import annotations

from typing import Any, Dict, List


def _uniq(seq: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in seq:
        x = (x or "").strip()
        if not x:
            continue
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def make_scorecard(req) -> Dict[str, Any]:
    """
    Builds the scorecard object expected by services/analyze.py and app.py.

    Compatibility:
    - Older code expects req.keywords. If absent, we derive from required+preferred.
    """
    required = _uniq(getattr(req, "required_skills", []) or [])
    preferred = _uniq(getattr(req, "preferred_skills", []) or [])

    keywords = getattr(req, "keywords", None)
    if not keywords:
        keywords = _uniq(required + preferred)

    return {
        "responsibilities": getattr(req, "responsibilities", []) or [],
        "must": required,
        "nice": preferred,
        "keywords_top": (keywords or [])[:30],
        # Keep grouped fields if your UI expects them later; otherwise safe defaults
        "must_grouped": {"all": required},
        "nice_grouped": {"all": preferred},
    }
