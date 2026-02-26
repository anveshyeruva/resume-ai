import streamlit as st

def render_status_badge(label: str, tone: str = "neutral"):
    """
    tone: "good" | "bad" | "warn" | "neutral"
    """
    tone_class = {
        "good": "ra-pill ra-pill-good",
        "bad": "ra-pill ra-pill-bad",
        "warn": "ra-pill ra-pill-warn",
        "neutral": "ra-pill ra-pill-neutral",
    }.get(tone, "ra-pill ra-pill-neutral")

    st.markdown(
        f"""
        <span class="{tone_class}">{label}</span>
        """,
        unsafe_allow_html=True,
    )

def inject_badge_css():
    st.markdown(
        """
        <style>
          .ra-pill {
            display:inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12.5px;
            font-weight: 700;
            border: 1px solid rgba(255,255,255,0.14);
            background: rgba(255,255,255,0.08);
            color: rgba(255,255,255,0.92);
            margin-right: 8px;
            margin-bottom: 6px;
          }
          .ra-pill-good  { background: rgba(46, 160, 67, 0.18); border-color: rgba(46, 160, 67, 0.35); }
          .ra-pill-bad   { background: rgba(248, 81, 73, 0.18); border-color: rgba(248, 81, 73, 0.35); }
          .ra-pill-warn  { background: rgba(245, 158, 11, 0.18); border-color: rgba(245, 158, 11, 0.35); }
          .ra-pill-neutral { background: rgba(255, 255, 255, 0.08); border-color: rgba(255,255,255,0.14); }
        </style>
        """,
        unsafe_allow_html=True,
    )
