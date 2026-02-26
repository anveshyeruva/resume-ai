import os
import json
import streamlit as st

from core.persistence import save_run
from core.jd_parser import parse_job_description, to_dict
from core.scorecard import make_scorecard
from core.gap_analysis import analyze_gaps
from core.draft_tailor import build_tailored_skills_section, suggest_bullet_enhancements
from export.docx_exporter import export_tailored_docx

# Sidebar collapsed by default (safe, no clicking)
st.set_page_config(page_title="Resume AI Builder", layout="wide", initial_sidebar_state="collapsed")

# -----------------------------
# Helpers (modern UI rendering)
# -----------------------------
def render_card(title: str, body_html: str):
    st.markdown(
        f"""
        <div class="ra-card">
          <div class="ra-card-title">{title}</div>
          <div class="ra-card-body">{body_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_chips(items):
    if not items:
        return '<span class="ra-muted">None</span>'
    chips = "".join([f'<span class="ra-chip">{str(x)}</span>' for x in items])
    return f'<div class="ra-chiprow">{chips}</div>'

def render_grouped_chips(title: str, grouped: dict):
    parts = [f'<div class="ra-card"><div class="ra-card-title">{title}</div><div class="ra-grid">']
    for cat, skills in grouped.items():
        chips = "".join([f'<span class="ra-chip">{s}</span>' for s in skills])
        parts.append(
            f"""
            <div class="ra-group">
              <div class="ra-group-title">{cat}</div>
              <div class="ra-chiprow">{chips}</div>
            </div>
            """
        )
    parts.append("</div></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

# -----------------------------
# CSS (dark-mode friendly, modern)
# -----------------------------
st.markdown(
    """
    <style>
      .block-container { padding-top: 2.6rem; }

      .ra-header {
        margin-top: 10px;
        padding: 18px 20px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.10);
        backdrop-filter: blur(8px);
      }
      .ra-row { display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; }
      .ra-icon {
        width: 44px; height: 44px; border-radius: 14px;
        display:flex; align-items:center; justify-content:center;
        background: rgba(56, 139, 253, 0.18);
        border: 1px solid rgba(56, 139, 253, 0.35);
        color: rgba(255,255,255,0.92);
        font-size: 22px; font-weight: 800;
        flex: 0 0 auto;
      }
      .ra-title { font-size: 34px; font-weight: 850; line-height: 1.1; margin: 0; color: rgba(255,255,255,0.95); }
      .ra-subtitle { margin-top: 8px; font-size: 15.5px; color: rgba(255,255,255,0.72); max-width: 980px; }

      .ra-badges { margin-top: 14px; display:flex; gap:10px; flex-wrap:wrap; }
      .ra-badge {
        font-size: 13px; padding: 6px 12px; border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        color: rgba(255,255,255,0.90);
        background: rgba(255,255,255,0.08);
        white-space: nowrap;
      }
      .ra-badge-blue  { background: rgba(56, 139, 253, 0.18); border-color: rgba(56, 139, 253, 0.35); }
      .ra-badge-green { background: rgba(46, 160, 67, 0.18);  border-color: rgba(46, 160, 67, 0.35); }
      .ra-badge-amber { background: rgba(245, 158, 11, 0.18); border-color: rgba(245, 158, 11, 0.35); }

      .ra-card {
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.10);
      }
      .ra-card-title { font-size: 15px; font-weight: 750; color: rgba(255,255,255,0.92); margin-bottom: 10px; }
      .ra-card-body { color: rgba(255,255,255,0.80); font-size: 14px; line-height: 1.5; }

      .ra-chiprow { display:flex; flex-wrap:wrap; gap:8px; }
      .ra-chip {
        font-size: 12.5px;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.08);
        color: rgba(255,255,255,0.88);
      }
      .ra-muted { color: rgba(255,255,255,0.65); }

      .ra-grid { display:grid; grid-template-columns: 1fr; gap: 12px; }
      @media (min-width: 900px) { .ra-grid { grid-template-columns: 1fr 1fr; } }
      .ra-group-title { font-size: 13px; font-weight: 750; margin-bottom: 8px; color: rgba(255,255,255,0.76); }

      button[data-baseweb="tab"] { padding-top: 10px; padding-bottom: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Session state
# -----------------------------
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "jd_text" not in st.session_state:
    st.session_state.jd_text = ""
if "base_resume" not in st.session_state:
    st.session_state.base_resume = ""

# -----------------------------
# Header
# -----------------------------
ai_status = "AI: Off (Friday: Remote Ollama)"
st.markdown(
    f"""
    <div class="ra-header">
      <div class="ra-row">
        <div class="ra-icon">⚙️</div>
        <div>
          <div class="ra-title">Resume AI Builder</div>
          <div class="ra-subtitle">
            Parse job requirements, measure fit, and generate a tailored resume draft (zero cost, local-first).
          </div>
          <div class="ra-badges">
            <span class="ra-badge ra-badge-blue">Mode: Draft</span>
            <span class="ra-badge ra-badge-green">Storage: Local</span>
            <span class="ra-badge ra-badge-amber">{ai_status}</span>
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# -----------------------------
# Inputs (main page, modern drawer-like expander)
# -----------------------------
with st.expander("Inputs (paste JD + base resume)", expanded=True):
    st.session_state.jd_text = st.text_area(
        "Job Description",
        value=st.session_state.jd_text,
        height=220,
        placeholder="Paste JD text here (recommended).",
    )
    st.session_state.base_resume = st.text_area(
        "Base Resume (master)",
        value=st.session_state.base_resume,
        height=220,
        placeholder="Paste your master resume text here.",
    )

    colA, colB, colC = st.columns([1, 1, 1])
    with colA:
        analyze_clicked = st.button("Analyze", use_container_width=True)
    with colB:
        export_clicked = st.button("Export Draft DOCX", use_container_width=True)
    with colC:
        save_clicked = st.button("Save Run JSON", use_container_width=True)

    reset_clicked = st.button("Reset session", use_container_width=True)

if reset_clicked:
    st.session_state.analysis = None
    st.session_state.jd_text = ""
    st.session_state.base_resume = ""
    st.rerun()

# -----------------------------
# Analyze
# -----------------------------
if analyze_clicked:
    jd_text = st.session_state.jd_text
    base_resume = st.session_state.base_resume

    if not jd_text.strip():
        st.error("Paste a job description first.")
    elif not base_resume.strip():
        st.error("Paste your base resume first.")
    else:
        req = parse_job_description(jd_text)
        score = make_scorecard(req)
        gaps = analyze_gaps(req, base_resume)
        tailored_skills = build_tailored_skills_section(req, base_resume)
        suggestions = suggest_bullet_enhancements(req, base_resume)

        st.session_state.analysis = {
            "jd_text": jd_text,
            "req": to_dict(req),
            "keywords_top": score["keywords_top"],
            "scorecard": score,
            "gaps": gaps,
            "matched_skills": tailored_skills["skills_matched_to_jd"],
            "suggestions": suggestions,
            "base_resume": base_resume,
        }

analysis = st.session_state.analysis

if not analysis:
    st.caption("Add inputs above, then click Analyze.")
    st.stop()

# -----------------------------
# Top metrics
# -----------------------------
must_missing = len(analysis["gaps"]["must_missing_high"])
nice_missing = len(analysis["gaps"]["nice_missing_high"])
must_present = len(analysis["gaps"]["must_present"])
nice_present = len(analysis["gaps"]["nice_present"])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Must-have present", must_present)
m2.metric("Must-have missing", must_missing)
m3.metric("Nice-to-have present", nice_present)
m4.metric("Nice-to-have missing", nice_missing)

st.write("")

# -----------------------------
# Tabs
# -----------------------------
tab_overview, tab_gaps, tab_tailor, tab_export, tab_debug = st.tabs(
    ["Overview", "Gaps", "Draft Tailoring", "Export", "Debug"]
)

with tab_overview:
    st.subheader("Overview")
    left, right = st.columns([1, 1])

    with left:
        body = "<ul style='margin:0; padding-left: 1.1rem;'>"
        for r in analysis["scorecard"]["responsibilities"]:
            body += f"<li>{r}</li>"
        body += "</ul>"
        render_card("Responsibilities (from JD)", body)

    with right:
        render_card("Top Keywords", render_chips(analysis["keywords_top"]))

    st.write("")
    st.subheader("Requirements Scorecard")
    c1, c2 = st.columns([1, 1])
    with c1:
        render_grouped_chips("Must-have (grouped)", analysis["scorecard"]["must_grouped"])
    with c2:
        render_grouped_chips("Nice-to-have (grouped)", analysis["scorecard"]["nice_grouped"])

with tab_gaps:
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

    st.caption(analysis["gaps"]["note"])

with tab_tailor:
    st.subheader("Draft Tailoring (No AI Yet)")
    render_card("Skills matched to JD (detected from your resume)", render_chips(analysis["matched_skills"]))

    sugg_html = "<ul style='margin:0; padding-left: 1.1rem;'>"
    for s in analysis["suggestions"]:
        sugg_html += f"<li>{s}</li>"
    sugg_html += "</ul>"

    st.write("")
    render_card("Suggestions (safe, rule-based)", sugg_html)

with tab_export:
    st.subheader("Export")
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "tailored_resume_draft.docx")

    colx, coly = st.columns([1, 1])

    with colx:
        render_card("Draft DOCX", "Exports a local draft with matched skills, suggestions, and your base resume.")
        st.write("")
        if export_clicked:
            export_tailored_docx(
                output_path=out_path,
                base_resume_text=analysis["base_resume"],
                matched_skills=analysis["matched_skills"],
                jd_keywords=analysis["keywords_top"],
                suggestions=analysis["suggestions"],
            )
            st.success("DOCX created successfully.")

        if os.path.exists(out_path):
            with open(out_path, "rb") as f:
                st.download_button(
                    label="Download tailored_resume_draft.docx",
                    data=f,
                    file_name="tailored_resume_draft.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

    with coly:
        render_card("Save Run (JSON)", "Saves this run locally under data/ so you can reload later. The data folder is ignored by Git.")
        st.write("")
        if save_clicked:
            p = save_run(analysis)
            st.success(f"Saved run: {p}")

with tab_debug:
    st.subheader("Debug")
    with st.expander("Detected Resume Skills"):
        skills = analysis["gaps"].get("resume_skills_detected", [])
        st.write(", ".join(skills) if skills else "None detected")

    with st.expander("Raw Parsed Requirements JSON"):
        st.code(json.dumps(analysis["req"], indent=2))

    with st.expander("Raw Analysis Object"):
        st.code(json.dumps(analysis, indent=2))
