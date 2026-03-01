# app.py

from __future__ import annotations

import hashlib
import io
import re
from urllib.parse import urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from docx import Document

from config import CONFIG
from logger import get_logger

from core.persistence import save_run
from ui.components import (
    inject_css,
    render_header,
    render_card,
    render_chips,
    render_grouped_chips,
    safe_debug_json,
)
from ui.sponsorship import render_sponsorship_section
from ui.badges import inject_badge_css, render_status_badge
from ui.sidebar import render_sidebar

from services.analyze import run_analysis
from services.exporter import ensure_docx_bytes
from services.ai_enhance import rewrite_responsibilities

log = get_logger("app")

st.set_page_config(
    page_title="Resume AI Builder",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()
inject_badge_css()
render_header()

# -----------------------
# Session init
# -----------------------
st.session_state.setdefault("analysis", None)

# JD inputs
st.session_state.setdefault("jd_url", "")
st.session_state.setdefault("jd_text", "")
st.session_state.setdefault("jd_source", "text")      # "text" or "paste"
st.session_state.setdefault("jd_paste_raw", "")
st.session_state.setdefault("jd_text_next", None)     # staged update before widget

# Resume inputs
st.session_state.setdefault("base_resume", "")
st.session_state.setdefault("resume_uploaded_name", None)
st.session_state.setdefault("resume_uploaded_chars", 0)

# Export cache
st.session_state.setdefault("docx_bytes", None)
st.session_state.setdefault("docx_sig", None)

# AI cache (per analysis run)
st.session_state.setdefault("analysis_run_id", None)
st.session_state.setdefault("ai_rewritten_resp", None)
st.session_state.setdefault("ai_error", None)

# Sidebar UI (sets ai_mode / keys etc.)
render_sidebar()

# -----------------------
# Helpers: JD URL fetch
# -----------------------
def _is_probably_linkedin(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return "linkedin.com" in host
    except Exception:
        return False


def _looks_like_login_wall(text: str) -> bool:
    t = (text or "").lower()
    # generic + linkedin-ish authwall phrases
    needles = [
        "sign in",
        "log in",
        "join linkedin",
        "authwall",
        "you’re signed out",
        "to continue",
        "captcha",
        "security verification",
    ]
    return any(n in t for n in needles)


def fetch_job_text_from_url(url: str) -> str:
    """
    Best-effort universal extractor for job posting pages.
    Many sites work (Greenhouse, Lever, Ashby, company career pages).
    LinkedIn often blocks with auth wall.
    """
    url = (url or "").strip()
    if not url:
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def clean_jd_text(t: str) -> str:
    t = (t or "").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def _stage_set_jd_text(new_text: str) -> None:
    # Stage update; it will be applied BEFORE jd_text widget is created.
    st.session_state["jd_text_next"] = new_text
    st.session_state["jd_source"] = "text"
    st.rerun()


def on_fetch_url_clicked() -> None:
    url = (st.session_state.get("jd_url") or "").strip()
    if not url:
        st.session_state["fetch_error"] = "Paste a job posting URL first."
        return

    try:
        text = fetch_job_text_from_url(url)
        if not text or len(text) < 300:
            # Too short to be a JD; likely blocked or bad parse
            if _is_probably_linkedin(url):
                st.session_state["jd_source"] = "paste"
                st.session_state["fetch_error"] = (
                    "LinkedIn blocked automated fetch. Use the Paste JD option below."
                )
            else:
                st.session_state["fetch_error"] = (
                    "Fetched text looks too short. Use Paste JD below or paste the JD manually."
                )
            return

        # If it smells like a login wall, route to paste mode
        if _looks_like_login_wall(text):
            st.session_state["jd_source"] = "paste"
            st.session_state["fetch_error"] = (
                "This site returned a login or verification page. Use Paste JD below."
            )
            return

        # Good: apply to JD box
        st.session_state["fetch_error"] = None
        _stage_set_jd_text(text)

    except Exception as e:
        st.session_state["fetch_error"] = f"Fetch failed: {e}"


def on_use_paste_clicked() -> None:
    st.session_state["jd_source"] = "paste"
    st.rerun()


def on_apply_paste_clicked() -> None:
    raw = st.session_state.get("jd_paste_raw", "")
    cleaned = clean_jd_text(raw)
    if not cleaned:
        st.session_state["fetch_error"] = "Paste the JD text first."
        return
    st.session_state["fetch_error"] = None
    _stage_set_jd_text(cleaned)


# -----------------------
# Helpers: Resume extraction
# -----------------------
def _extract_docx_text(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # lazy import
    except Exception as e:
        raise RuntimeError("PDF support needs pypdf. Install: pip install pypdf") from e

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        txt = (page.extract_text() or "").strip()
        if txt:
            parts.append(txt)
    return "\n\n".join(parts).strip()


def extract_resume_text(uploaded_file) -> str:
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.getvalue()
    if name.endswith(".docx"):
        return _extract_docx_text(data)
    if name.endswith(".pdf"):
        return _extract_pdf_text(data)
    raise RuntimeError("Unsupported file type. Upload a DOCX or PDF.")


# -----------------------
# Helpers: run id + UI formatting
# -----------------------
def _make_run_id(jd_text: str, base_resume: str) -> str:
    payload = "\n".join(
        [
            jd_text.strip(),
            "---RESUME---",
            base_resume.strip(),
            "---AI---",
            st.session_state.get("ai_mode", "off"),
            st.session_state.get("ollama_base_url", ""),
            st.session_state.get("ollama_model", ""),
            st.session_state.get("cloud_provider", ""),
            st.session_state.get("openai_model", ""),
            "HAS_OPENAI_KEY" if bool(st.session_state.get("openai_api_key")) else "NO_OPENAI_KEY",
        ]
    ).encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()[:16]


def _is_noise(line: str) -> bool:
    s = (line or "").strip().lower()
    return (
        "salary" in s
        or "compensation" in s
        or ("$" in s and "range" in s)
        or s.startswith("the salary")
        or s.startswith("salary range")
    )


def _scroll_list_html(items: list[str], max_height_px: int = 360) -> str:
    body = f"""
<div style="max-height: {max_height_px}px; overflow-y: auto; padding-right: 6px;">
  <ul style="margin:0; padding-left: 1.1rem;">
"""
    for r in items:
        body += f"<li>{r}</li>"
    body += """
  </ul>
</div>
"""
    return body


# -----------------------
# Inputs
# -----------------------
with st.expander("Inputs", expanded=True):
    st.text_input(
        "Job posting URL (optional)",
        key="jd_url",
        placeholder="Paste any job posting URL (LinkedIn, Greenhouse, Lever, Ashby, company site, etc.)",
        help="We will try to fetch text. If blocked, use Paste JD below.",
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.button("Fetch from URL", use_container_width=True, on_click=on_fetch_url_clicked)
    with c2:
        st.button("Paste JD instead", use_container_width=True, on_click=on_use_paste_clicked)
    with c3:
        url_val = (st.session_state.get("jd_url") or "").strip()
        st.link_button("Open in browser", url_val if url_val else "https://www.google.com")

    if st.session_state.get("fetch_error"):
        st.warning(st.session_state["fetch_error"])

    # Paste workflow (for LinkedIn / login-walled sites)
    if st.session_state.get("jd_source") == "paste":
        st.text_area(
            "Paste job description text here (recommended for LinkedIn)",
            key="jd_paste_raw",
            height=180,
            placeholder="Open job posting → expand full description → copy → paste here",
        )
        st.button("Clean and apply pasted JD", use_container_width=True, on_click=on_apply_paste_clicked)

    # Apply staged JD text BEFORE the jd_text widget is created
    if st.session_state.get("jd_text_next") is not None:
        st.session_state["jd_text"] = st.session_state["jd_text_next"]
        st.session_state["jd_text_next"] = None

    st.text_area(
        "Job Description",
        key="jd_text",
        height=220,
        placeholder="Paste JD text here, or fetch from a URL above.",
    )

    # Resume upload
    uploaded_resume = st.file_uploader(
        "Upload Resume (DOCX or PDF)",
        type=["docx", "pdf"],
        accept_multiple_files=False,
        help="Upload your master resume. Text is extracted into Base Resume.",
    )

    if uploaded_resume is not None:
        try:
            resume_text = extract_resume_text(uploaded_resume)
            if not resume_text.strip():
                st.error("Uploaded file loaded, but extracted text is empty.")
            else:
                st.session_state["base_resume"] = resume_text
                st.session_state["resume_uploaded_name"] = uploaded_resume.name
                st.session_state["resume_uploaded_chars"] = len(resume_text)
                st.success(
                    f"Loaded: {uploaded_resume.name} ({st.session_state['resume_uploaded_chars']} characters)"
                )
        except Exception as e:
            st.error(str(e))

    # Optional override
    st.text_area(
        "Base Resume (optional override)",
        key="base_resume",
        height=220,
        placeholder="If you want, paste or edit resume text here after upload.",
    )

    if st.session_state.get("resume_uploaded_name"):
        with st.expander("Resume extraction preview", expanded=False):
            preview_lines = (st.session_state.get("base_resume", "") or "").splitlines()[:35]
            st.code("\n".join(preview_lines) if preview_lines else "(empty)")

    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        analyze_clicked = st.button("Analyze", use_container_width=True, type="primary")
    with colB:
        export_main_clicked = st.button(
            "Export Draft DOCX",
            use_container_width=True,
            disabled=not CONFIG.ff_show_export,
        )
    with colC:
        save_clicked = st.button(
            "Save Run",
            use_container_width=True,
            disabled=not CONFIG.ff_allow_save_run,
        )

    colR1, colR2 = st.columns([1, 1])
    with colR1:
        reset_clicked = st.button("Reset session", use_container_width=True)
    with colR2:
        clear_resume_clicked = st.button("Clear resume text", use_container_width=True)

if clear_resume_clicked:
    st.session_state["base_resume"] = ""
    st.session_state["resume_uploaded_name"] = None
    st.session_state["resume_uploaded_chars"] = 0
    st.rerun()

if reset_clicked:
    st.session_state["analysis"] = None

    st.session_state["jd_url"] = ""
    st.session_state["jd_text"] = ""
    st.session_state["jd_source"] = "text"
    st.session_state["jd_paste_raw"] = ""
    st.session_state["jd_text_next"] = None
    st.session_state["fetch_error"] = None

    st.session_state["base_resume"] = ""
    st.session_state["resume_uploaded_name"] = None
    st.session_state["resume_uploaded_chars"] = 0

    st.session_state["docx_bytes"] = None
    st.session_state["docx_sig"] = None

    st.session_state["analysis_run_id"] = None
    st.session_state["ai_rewritten_resp"] = None
    st.session_state["ai_error"] = None
    st.rerun()

# -----------------------
# Analyze
# -----------------------
if analyze_clicked:
    jd_text = st.session_state.get("jd_text", "")
    base_resume = st.session_state.get("base_resume", "")

    if not jd_text.strip():
        st.error("Add a Job Description first (fetch from URL or paste).")
    elif not base_resume.strip():
        st.error("Upload a resume (DOCX or PDF) or paste your base resume text first.")
    else:
        try:
            analysis = run_analysis(jd_text, base_resume)
            st.session_state["analysis"] = analysis

            # reset export cache
            st.session_state["docx_bytes"] = None
            st.session_state["docx_sig"] = None

            # run id (inputs + ai settings)
            run_id = _make_run_id(jd_text, base_resume)
            if run_id != st.session_state.get("analysis_run_id"):
                st.session_state["analysis_run_id"] = run_id
                st.session_state["ai_rewritten_resp"] = None
                st.session_state["ai_error"] = None

            # AI enhancement (optional)
            if st.session_state.get("ai_mode", "off") != "off":
                if st.session_state.get("ai_mode") == "cloud" and not st.session_state.get("openai_api_key"):
                    st.session_state["ai_error"] = "Cloud mode selected but API key is missing."
                else:
                    if st.session_state.get("ai_rewritten_resp") is None and st.session_state.get("ai_error") is None:
                        base_bullets = analysis.get("responsibilities") or analysis["scorecard"].get(
                            "responsibilities", []
                        )
                        ai_out = rewrite_responsibilities(
                            base_bullets,
                            jd_keywords=analysis.get("keywords_top", []),
                            ai_mode=st.session_state["ai_mode"],
                            ollama_base_url=st.session_state["ollama_base_url"],
                            ollama_model=st.session_state["ollama_model"],
                            cloud_provider=st.session_state["cloud_provider"],
                            openai_api_key=st.session_state["openai_api_key"],
                            openai_model=st.session_state["openai_model"],
                        )
                        st.session_state["ai_rewritten_resp"] = ai_out.get("rewritten")
                        st.session_state["ai_error"] = ai_out.get("error")

            st.success("Analysis complete. Check the tabs below.")
        except Exception as e:
            log.exception("Analyze failed")
            st.exception(e)

analysis = st.session_state.get("analysis")
if not analysis:
    st.caption("Add inputs above, then click Analyze.")
    st.stop()

# -----------------------
# Optional export trigger
# -----------------------
if CONFIG.ff_show_export and export_main_clicked:
    try:
        ensure_docx_bytes(analysis, st.session_state, force=True)
        st.success("Draft DOCX is ready in the Export tab.")
    except Exception as e:
        log.exception("Export failed")
        st.exception(e)

# -----------------------
# Metrics (weighted)
# -----------------------
must_missing_high = analysis["gaps"]["must_missing_high"]
must_missing_maybe = analysis["gaps"]["must_missing_maybe"]
nice_missing_high = analysis["gaps"]["nice_missing_high"]
nice_missing_maybe = analysis["gaps"]["nice_missing_maybe"]

must_present = len(analysis["gaps"]["must_present"])
nice_present = len(analysis["gaps"]["nice_present"])

must_missing_score = len(must_missing_high) + 0.5 * len(must_missing_maybe)
nice_missing_score = len(nice_missing_high) + 0.5 * len(nice_missing_maybe)

must_total = must_present + must_missing_score
nice_total = nice_present + nice_missing_score

must_pct = (must_present / must_total) if must_total else 0.0
nice_pct = (nice_present / nice_total) if nice_total else 0.0
overall_pct = (0.70 * must_pct) + (0.30 * nice_pct)

must_missing_count = len(must_missing_high) + len(must_missing_maybe)
nice_missing_count = len(nice_missing_high) + len(nice_missing_maybe)

m0, m1, m2, m3, m4 = st.columns([1.2, 1, 1, 1, 1])
m0.metric("Match %", f"{overall_pct * 100:.0f}%")
m1.metric("Must-have present", must_present)
m2.metric("Must-have missing", must_missing_count)
m3.metric("Nice-to-have present", nice_present)
m4.metric("Nice-to-have missing", nice_missing_count)

st.caption(
    f"Must-have match: {must_pct * 100:.0f}%  |  Nice-to-have match: {nice_pct * 100:.0f}%  |  Overall: {overall_pct * 100:.0f}%"
)
st.progress(overall_pct)

# -----------------------
# Sponsorship badge (simple)
# -----------------------
if not CONFIG.ff_show_sponsorship:
    try:
        spon = analysis.get("sponsorship") or {}
        status = (spon.get("status") or "").lower()

        if "available" in status and "not" not in status:
            render_status_badge("✅ Sponsor", "good")
        elif "not available" in status or "implied" in status:
            render_status_badge("❌ No sponsor", "bad")
        elif "conflicting" in status:
            render_status_badge("⚠️ Conflicting", "warn")
        else:
            render_status_badge("⚪ Not specified", "neutral")
    except Exception:
        render_status_badge("⚪ Not specified", "neutral")

st.write("")
st.write("")

# -----------------------
# Tabs
# -----------------------
tab_names = ["Overview"]
if CONFIG.ff_show_gaps:
    tab_names.append("Gaps")
if CONFIG.ff_show_tailoring:
    tab_names.append("Draft Tailoring")
if CONFIG.ff_show_export:
    tab_names.append("Export")
if CONFIG.debug_ui:
    tab_names.append("Debug")

tabs = st.tabs(tab_names)
tab_map = {name: tabs[i] for i, name in enumerate(tab_names)}

# -----------------------
# Overview
# -----------------------
with tab_map["Overview"]:
    st.subheader("Overview")
    left, right = st.columns([1, 1])

    with left:
        resp = (analysis.get("responsibilities") or analysis["scorecard"].get("responsibilities", []))
        resp = [r for r in resp if not _is_noise(r)]
        render_card("Responsibilities (from JD)", _scroll_list_html(resp, max_height_px=360))

        if st.session_state.get("ai_mode", "off") != "off":
            if st.session_state.get("ai_error"):
                render_card("AI Rewrite (Responsibilities)", f"<b>Skipped:</b> {st.session_state['ai_error']}")
            elif st.session_state.get("ai_rewritten_resp"):
                ai_resp = st.session_state["ai_rewritten_resp"]
                render_card("AI Rewrite (Responsibilities)", _scroll_list_html(ai_resp, max_height_px=360))

    with right:
        render_card("Top Keywords", render_chips(analysis["keywords_top"]))

    if CONFIG.ff_show_sponsorship:
        st.write("")
        render_sponsorship_section(analysis.get("jd_text", ""))

    if CONFIG.ff_show_scorecard:
        st.write("")
        st.subheader("Requirements Scorecard")
        c1, c2 = st.columns([1, 1])
        with c1:
            render_grouped_chips("Must-have (grouped)", analysis["scorecard"]["must_grouped"])
        with c2:
            render_grouped_chips("Nice-to-have (grouped)", analysis["scorecard"]["nice_grouped"])

# -----------------------
# Gaps
# -----------------------
if CONFIG.ff_show_gaps:
    with tab_map["Gaps"]:
        st.subheader("Gap Analysis")
        g1, g2 = st.columns([1, 1])

        with g1:
            render_card("Must-have present", render_chips(analysis["gaps"]["must_present"]))
            st.write("")
            render_card("Must-have missing (high confidence)", render_chips(analysis["gaps"]["must_missing_high"]))
            st.write("")
            render_card("Must-have missing (maybe)", render_chips(analysis["gaps"]["must_missing_maybe"]))

        with g2:
            render_card("Nice-to-have present", render_chips(analysis["gaps"]["nice_present"]))
            st.write("")
            render_card("Nice-to-have missing (high confidence)", render_chips(analysis["gaps"]["nice_missing_high"]))
            st.write("")
            render_card("Nice-to-have missing (maybe)", render_chips(analysis["gaps"]["nice_missing_maybe"]))

        note = analysis["gaps"].get("note", "")
        if note:
            st.caption(note)

# -----------------------
# Tailoring
# -----------------------
if CONFIG.ff_show_tailoring:
    with tab_map["Draft Tailoring"]:
        st.subheader("Draft Tailoring")
        render_card("Skills matched to JD (detected from your resume)", render_chips(analysis["matched_skills"]))

        sugg_html = "<ul style='margin:0; padding-left: 1.1rem;'>"
        for s in analysis["suggestions"]:
            sugg_html += f"<li>{s}</li>"
        sugg_html += "</ul>"

        st.write("")
        render_card("Suggestions", sugg_html)

# -----------------------
# Export
# -----------------------
if CONFIG.ff_show_export:
    with tab_map["Export"]:
        st.subheader("Export")
        colx, coly = st.columns([1, 1])

        with colx:
            render_card("Draft DOCX", "Download a tailored draft based on the current analysis.")
            st.write("")

            try:
                if CONFIG.export_auto_build:
                    docx_bytes = ensure_docx_bytes(analysis, st.session_state, force=False)
                    st.download_button(
                        label="Download tailored_resume_draft.docx",
                        data=docx_bytes,
                        file_name="tailored_resume_draft.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                else:
                    st.info("Auto-build disabled. Use 'Export Draft DOCX' button above.")
            except Exception as e:
                log.exception("Export tab build failed")
                st.exception(e)

            st.write("")
            if st.button("Regenerate DOCX", use_container_width=True):
                try:
                    docx_bytes = ensure_docx_bytes(analysis, st.session_state, force=True)
                    st.success("DOCX regenerated.")
                    st.download_button(
                        label="Download tailored_resume_draft.docx",
                        data=docx_bytes,
                        file_name="tailored_resume_draft.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                except Exception as e:
                    log.exception("Regenerate failed")
                    st.exception(e)

        with coly:
            render_card("Save Run", "Save this run locally so you can reload it later.")
            st.write("")
            if CONFIG.ff_allow_save_run and save_clicked:
                try:
                    save_run(analysis)
                    st.success("Run saved.")
                except Exception as e:
                    log.exception("Save failed")
                    st.exception(e)

# -----------------------
# Debug
# -----------------------
if CONFIG.debug_ui and "Debug" in tab_map:
    with tab_map["Debug"]:
        st.subheader("Debug")
        safe_debug_json(CONFIG.debug_ui, "Parsed Requirements", analysis.get("req"))
        safe_debug_json(CONFIG.debug_ui, "Analysis Object", analysis)
