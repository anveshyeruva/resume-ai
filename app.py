# app.py

import hashlib
import streamlit as st

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
from ui.sidebar import render_sidebar  # unified sidebar

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
st.session_state.setdefault("jd_text", "")
st.session_state.setdefault("base_resume", "")
st.session_state.setdefault("docx_bytes", None)
st.session_state.setdefault("docx_sig", None)

# AI cache (per analysis "run")
st.session_state.setdefault("analysis_run_id", None)
st.session_state.setdefault("ai_rewritten_resp", None)
st.session_state.setdefault("ai_error", None)

# Sidebar UI
render_sidebar()


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
    """
    Filters out common non-responsibility text that often shows up in JDs.
    """
    s = (line or "").strip().lower()
    return (
        "salary" in s
        or "compensation" in s
        or ("$" in s and "range" in s)
        or s.startswith("the salary")
        or s.startswith("salary range")
    )


def _scroll_list_html(items: list[str], max_height_px: int = 360) -> str:
    """
    Render a scrollable UL in a fixed-height container.
    """
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
    st.text_area("Job Description", key="jd_text", height=220, placeholder="Paste JD text here.")
    st.text_area("Base Resume", key="base_resume", height=220, placeholder="Paste your master resume text here.")

    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        analyze_clicked = st.button("Analyze", use_container_width=True)
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

    reset_clicked = st.button("Reset session", use_container_width=True)

if reset_clicked:
    st.session_state["analysis"] = None
    st.session_state["jd_text"] = ""
    st.session_state["base_resume"] = ""
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
        st.error("Paste a job description first.")
    elif not base_resume.strip():
        st.error("Paste your base resume first.")
    else:
        try:
            analysis = run_analysis(jd_text, base_resume)
            st.session_state["analysis"] = analysis

            # reset export cache
            st.session_state["docx_bytes"] = None
            st.session_state["docx_sig"] = None

            # Compute run id (inputs + AI settings)
            run_id = _make_run_id(jd_text, base_resume)
            if run_id != st.session_state.get("analysis_run_id"):
                st.session_state["analysis_run_id"] = run_id
                st.session_state["ai_rewritten_resp"] = None
                st.session_state["ai_error"] = None

            # AI enhancement (optional): rewrite JD responsibilities once per run_id
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

# Weight "maybe missing" at 0.5 so it's a softer penalty than "high confidence missing"
must_missing_score = len(must_missing_high) + 0.5 * len(must_missing_maybe)
nice_missing_score = len(nice_missing_high) + 0.5 * len(nice_missing_maybe)

must_total = must_present + must_missing_score
nice_total = nice_present + nice_missing_score

must_pct = (must_present / must_total) if must_total else 0.0
nice_pct = (nice_present / nice_total) if nice_total else 0.0
overall_pct = (0.70 * must_pct) + (0.30 * nice_pct)

# Keep the counts as integers for display
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
# Show ONLY when detailed sponsorship section is OFF (no duplicate)
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
        # Responsibilities (filtered + scrollable)
        resp = (analysis.get("responsibilities") or analysis["scorecard"].get("responsibilities", []))
        resp = [r for r in resp if not _is_noise(r)]
        render_card("Responsibilities (from JD)", _scroll_list_html(resp, max_height_px=360))

        # AI rewrite (scrollable)
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
