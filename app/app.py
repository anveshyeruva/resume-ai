import os
import json
import streamlit as st

from core.persistence import save_run
from core.jd_parser import parse_job_description, to_dict
from core.scorecard import make_scorecard
from core.gap_analysis import analyze_gaps
from core.draft_tailor import build_tailored_skills_section, suggest_bullet_enhancements
from export.docx_exporter import export_tailored_docx

st.set_page_config(page_title="Resume AI Builder", layout="wide")
st.title("Resume AI Builder - Step 6 (Draft Tailoring + DOCX Export + Save Run)")

colA, colB = st.columns([1, 1])

with colA:
    jd_text = st.text_area("Paste Job Description Text", height=320, placeholder="Paste JD here...")

with colB:
    base_resume = st.text_area("Paste Base Resume Text (master)", height=320, placeholder="Paste your base resume here...")

# Initialize session state storage
if "analysis" not in st.session_state:
    st.session_state.analysis = None

if st.button("Analyze and Draft Tailor", key="analyze_btn"):
    if not jd_text.strip():
        st.error("Paste a job description first.")
    elif not base_resume.strip():
        st.error("Paste your base resume text first.")
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
            "gaps": gaps,
            "matched_skills": tailored_skills["skills_matched_to_jd"],
            "suggestions": suggestions,
            "base_resume": base_resume,
        }

analysis = st.session_state.analysis

if analysis:
    st.subheader("Gap Analysis (JD vs Your Resume)")
    g1, g2 = st.columns([1, 1])
    with g1:
        st.markdown("### Must-have missing (high confidence)")
        st.write(", ".join(analysis["gaps"]["must_missing_high"]) if analysis["gaps"]["must_missing_high"] else "None")
        st.markdown("### Nice-to-have missing (high confidence)")
        st.write(", ".join(analysis["gaps"]["nice_missing_high"]) if analysis["gaps"]["nice_missing_high"] else "None")
    with g2:
        st.markdown("### Must-have present")
        st.write(", ".join(analysis["gaps"]["must_present"]) if analysis["gaps"]["must_present"] else "None detected")
        st.markdown("### Nice-to-have present")
        st.write(", ".join(analysis["gaps"]["nice_present"]) if analysis["gaps"]["nice_present"] else "None detected")

    st.subheader("Draft Tailoring Output (No AI Yet)")
    st.markdown("### Skills matched to JD (detected from your resume)")
    st.write(", ".join(analysis["matched_skills"]) if analysis["matched_skills"] else "No matches detected")

    st.markdown("### Suggestions (safe, rule-based)")
    for s in analysis["suggestions"]:
        st.write(f"- {s}")

    st.subheader("Export and Save")
    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", "tailored_resume_draft.docx")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Export Draft DOCX", key="export_btn"):
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
                )

    with col2:
        if st.button("Save Run (JSON)", key="save_btn"):
            p = save_run(analysis)
            st.success(f"Saved: {p}")

    with st.expander("Raw Parsed Requirements JSON"):
        st.code(json.dumps(analysis["req"], indent=2))
else:
    st.info("Run Analyze and Draft Tailor first, then export or save.")
