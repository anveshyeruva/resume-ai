from __future__ import annotations

def build_bullet_rewrite_prompt(
    bullets: list[str],
    jd_keywords: list[str] | None = None,
) -> str:
    bullets_text = "\n".join(f"- {b}" for b in bullets if str(b).strip())
    kw_text = ", ".join((jd_keywords or [])[:20])

    return f"""
You are a resume assistant. Rewrite the bullets to be ATS-friendly and impact-focused.

Rules:
- Keep each bullet one line.
- Start with a strong action verb.
- Preserve meaning. Do not invent tools, employers, or metrics.
- If a metric is already present, keep it. If not present, do not add new numbers.
- Prefer concrete tech keywords when truthful: {kw_text}
- Avoid fluff and filler.

Input bullets:
{bullets_text}

Return ONLY the rewritten bullets, one per line starting with "-".
""".strip()
