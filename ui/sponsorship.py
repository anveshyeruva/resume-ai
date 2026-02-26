import re
import streamlit as st

NEG_STRONG = [
    ("No sponsorship", r"\b(no|without)\s+(visa\s+)?sponsorship\b"),
    ("Sponsorship not available", r"\b(visa\s+)?sponsorship\s+not\s+available\b"),
    ("No visa sponsorship", r"\bno\s+visa\s+sponsorship\b"),
    ("US citizen required", r"\b(us\s+citizen(ship)?|u\.s\.\s+citizen)\s+(required|only)\b"),
    ("Green card required", r"\b(green\s+card|permanent\s+resident)\s+(required|only)\b"),
    ("Must be US Person", r"\b(u\.s\.\s+person|us\s+person)\b"),
]

NEG_IMPLIED = [
    ("Must be authorized now and in future", r"\bauthorized\s+to\s+work\s+in\s+the\s+u\.?s\.?\b.*\b(now|currently)\b.*\b(future)\b"),
    ("Authorized without sponsorship", r"\bauthorized\s+to\s+work\s+in\s+the\s+u\.?s\.?\s+without\s+(visa\s+)?sponsorship\b"),
    ("No OPT or CPT", r"\b(no\s+opt|no\s+cpt|opt\s+not\s+accepted|cpt\s+not\s+accepted)\b"),
]

CONTRACTING = [
    ("W2 only", r"\bw2\s+only\b"),
    ("No C2C", r"\b(no\s+c2c|no\s+corp[-\s]?to[-\s]?corp|no\s+c2c\s+or\s+1099)\b"),
]

POSITIVE = [
    ("Sponsorship available", r"\b(visa\s+)?sponsorship\s+(available|provided|offered)\b"),
    ("Will sponsor", r"\b(will|can)\s+sponsor\b"),
    ("Open to sponsorship", r"\b(open\s+to|consider)\s+(visa\s+)?sponsorship\b"),
]

def _match_any(text: str, patterns):
    hits = []
    for label, pat in patterns:
        if re.search(pat, text or "", flags=re.IGNORECASE | re.DOTALL):
            hits.append(label)
    return hits

def sponsorship_summary(jd_text: str) -> dict:
    text = jd_text or ""
    pos = _match_any(text, POSITIVE)
    neg_strong = _match_any(text, NEG_STRONG)
    neg_implied = _match_any(text, NEG_IMPLIED)
    contracting = _match_any(text, CONTRACTING)

    if pos and (neg_strong or neg_implied):
        status = "Conflicting signals"
        detail = "Both sponsorship-friendly and restrictive wording found."
        level = "warning"
    elif pos:
        status = "Sponsorship: Available"
        detail = "Job post indicates they may sponsor."
        level = "success"
    elif neg_strong:
        status = "Sponsorship: Not available"
        detail = "Job post contains restrictive work authorization language."
        level = "error"
    elif neg_implied:
        status = "Sponsorship: Unclear (restriction language detected)"
        detail = "JD contains work authorization language. Verify with recruiter whether OPT and future sponsorship are accepted."
        level = "warning"
    else:
        status = "Sponsorship: Not specified"
        detail = "Job post does not clearly mention sponsorship or work authorization requirements."
        level = "info"

    return {
        "status": status,
        "detail": detail,
        "level": level,
        "signals": {
            "positive": pos,
            "restrictive": neg_strong + neg_implied,
            "contracting": contracting,
        },
    }

# Compatibility for older imports
def analyze_sponsorship(jd_text: str) -> dict:
    return sponsorship_summary(jd_text)

def render_sponsorship_section(jd_text: str):
    st.subheader("Sponsorship and Work Authorization")
    out = sponsorship_summary(jd_text)

    if out["level"] == "success":
        st.success(out["status"])
    elif out["level"] == "warning":
        st.warning(out["status"])
    elif out["level"] == "error":
        st.error(out["status"])
    else:
        st.info(out["status"])

    st.caption(out["detail"])

    sig = out["signals"]
    if sig["restrictive"]:
        st.markdown("**Restrictions found:** " + ", ".join(sig["restrictive"]))
    if sig["positive"]:
        st.markdown("**Sponsorship-friendly:** " + ", ".join(sig["positive"]))
    if sig["contracting"]:
        st.markdown("**Contracting constraints:** " + ", ".join(sig["contracting"]))