import json
import textwrap
import streamlit as st

def inject_css():
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
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_header():
    st.markdown(
        """
<div class="ra-header">
  <div class="ra-row">
    <div class="ra-icon">⚙️</div>
    <div>
      <div class="ra-title">Resume AI Builder</div>
      <div class="ra-subtitle">
        Paste a job description and your base resume to analyze fit and export a tailored draft.
      </div>
      <div class="ra-badges">
        <span class="ra-badge ra-badge-blue">Mode: Draft</span>
        <span class="ra-badge ra-badge-green">Storage: Local</span>
      </div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

def render_card(title: str, body_html: str):
    html = f"""
<div class="ra-card">
  <div class="ra-card-title">{title}</div>
  <div class="ra-card-body">{body_html}</div>
</div>
"""
    st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)

def render_chips(items):
    if not items:
        return '<span class="ra-muted">None</span>'
    chips = "".join([f'<span class="ra-chip">{str(x)}</span>' for x in items])
    return f'<div class="ra-chiprow">{chips}</div>'

def render_grouped_chips(title: str, grouped: dict):
    # Build HTML without leading indentation (avoid markdown code-block rendering)
    parts = [f'<div class="ra-card"><div class="ra-card-title">{title}</div><div class="ra-grid">']

    for cat, skills in (grouped or {}).items():
        # skills should be list-like; if it's a string, wrap it
        if isinstance(skills, str):
            skills = [skills]
        # Deduplicate while preserving order (case-insensitive)
        seen = set()
        deduped = []
        for s in (skills or []):
            k = str(s).strip().lower()
            if k and k not in seen:
                seen.add(k)
                deduped.append(s)
        skills = deduped
        chips = "".join([f'<span class="ra-chip">{s}</span>' for s in (skills or [])])
        block = f"""
<div class="ra-group">
  <div class="ra-group-title">{cat}</div>
  <div class="ra-chiprow">{chips}</div>
</div>
"""
        parts.append(textwrap.dedent(block).strip())

    parts.append("</div></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

def safe_debug_json(debug: bool, label: str, obj):
    if not debug:
        return
    with st.expander(f"Debug: {label}"):
        st.code(json.dumps(obj, indent=2))