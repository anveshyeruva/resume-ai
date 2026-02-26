import os
import hashlib
from export.docx_exporter import export_tailored_docx
from config import CONFIG
from logger import get_logger

log = get_logger("services.exporter")

def _sha_short(text: str) -> str:
    h = hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()
    return h[:12]

def ensure_docx_bytes(analysis: dict, session_state, force: bool = False) -> bytes:
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "tailored_resume_draft.docx")

    sig = (
        _sha_short(analysis.get("jd_text", ""))
        + "-"
        + _sha_short(analysis.get("base_resume", ""))
        + "-"
        + _sha_short(",".join(analysis.get("matched_skills", [])[:200]))
        + "-"
        + _sha_short(",".join(analysis.get("keywords_top", [])[:200]))
        + "-"
        + _sha_short(",".join(analysis.get("suggestions", [])[:200]))
    )

    cache_ok = CONFIG.export_cache_enabled and (not force)
    if cache_ok and session_state.get("docx_bytes") and (session_state.get("docx_sig") == sig):
        return session_state["docx_bytes"]

    log.info("Building DOCX export (force=%s, cache=%s)", force, CONFIG.export_cache_enabled)

    export_tailored_docx(
        output_path=out_path,
        base_resume_text=analysis["base_resume"],
        matched_skills=analysis["matched_skills"],
        jd_keywords=analysis["keywords_top"],
        suggestions=analysis["suggestions"],
    )

    with open(out_path, "rb") as f:
        b = f.read()

    session_state["docx_bytes"] = b
    session_state["docx_sig"] = sig
    return b
