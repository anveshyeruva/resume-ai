from typing import Dict, Tuple
from core.jd_parser import JobRequirements
from core.resume_parser import extract_resume_skills

# Derived "maybe" logic (soft inference)
DERIVED_MAYBE = {
    "unix": ["linux"],
    "ci": ["cicd"],
    "cd": ["cicd"],
}

# Skills that should NOT dominate scoring (too generic)
GENERIC_SKILLS = {
    "cloud", "agile", "metrics", "dashboards", "alarms", "apm",
}

# High-signal / hard requirements for platform + deployment tooling JDs
HARD_SKILLS = {
    "gitops", "argocd", "fluxcd", "bazel", "circleci",
    "helm", "eks", "ecs", "lambda",
    "prometheus", "grafana", "cloudwatch",
}

# Weighting roughly aligned with ATS “hard skills matter most”
def _weight(skill: str) -> float:
    s = (skill or "").strip().lower()
    if s in HARD_SKILLS:
        return 3.0
    if s in {"terraform", "kubernetes", "docker", "aws", "azure", "gcp", "python", "go", "ruby", "java"}:
        return 2.0
    if s in GENERIC_SKILLS:
        return 0.5
    return 1.0

def _split_missing(missing_list, resume_skills_set):
    missing_high = []
    missing_maybe = []
    for m in missing_list:
        implied_by = DERIVED_MAYBE.get(m, [])
        if any(x in resume_skills_set for x in implied_by):
            missing_maybe.append(m)
        else:
            missing_high.append(m)
    return missing_high, missing_maybe

def _weighted_coverage(present: list[str], missing_high: list[str], missing_maybe: list[str]) -> float:
    # maybe-missing counts as half-missing (ATS sometimes treats near matches as partial)
    total = 0.0
    got = 0.0
    for s in present:
        w = _weight(s); total += w; got += w
    for s in missing_high:
        total += _weight(s)
    for s in missing_maybe:
        total += _weight(s) * 0.75  # still penalize, but not as harsh as high-missing
        got += 0.0
    if total <= 0.0:
        return 0.0
    return got / total

def _cap_realistically(overall: float, must_missing_high: list[str], jd_required: list[str]) -> Tuple[float, str | None]:
    # ATS-like cap: never show 100 unless the JD has enough distinct requirements AND none are missing
    # This prevents “perfect” scores from tiny/overly generic requirement sets.
    if overall <= 0.0:
        return 0.0, None
    if len(jd_required) < 8:
        # not enough signal to claim near-perfect match
        return min(overall, 0.92), "Capped because the JD requirements extracted were too generic or too small."
    if must_missing_high:
        return min(overall, 0.97), "Capped because some required skills are missing."
    # even when nothing missing, keep a small cap to avoid “magic perfect”
    return min(overall, 0.985), None

def analyze_gaps(req: JobRequirements, resume_text: str) -> Dict:
    resume_skills = set(extract_resume_skills(resume_text))

    must = set(req.required_skills)
    nice = set(req.preferred_skills)

    must_present = sorted(must & resume_skills)
    must_missing_raw = sorted(must - resume_skills)

    nice_present = sorted(nice & resume_skills)
    nice_missing_raw = sorted(nice - resume_skills)

    must_missing_high, must_missing_maybe = _split_missing(must_missing_raw, resume_skills)
    nice_missing_high, nice_missing_maybe = _split_missing(nice_missing_raw, resume_skills)

    must_cov = _weighted_coverage(must_present, must_missing_high, must_missing_maybe)
    nice_cov = _weighted_coverage(nice_present, nice_missing_high, nice_missing_maybe)

    # ATS-like weighting (required dominates)
    overall = 0.75 * must_cov + 0.25 * nice_cov

    overall, cap_reason = _cap_realistically(overall, must_missing_high, req.required_skills)

    return {
        "resume_skills_detected": sorted(resume_skills),

        "must_present": must_present,
        "must_missing_high": must_missing_high,
        "must_missing_maybe": must_missing_maybe,

        "nice_present": nice_present,
        "nice_missing_high": nice_missing_high,
        "nice_missing_maybe": nice_missing_maybe,

        # New: ATS-like match score block
        "match": {
            "must_pct": must_cov,
            "nice_pct": nice_cov,
            "overall_pct": overall,
            "cap_reason": cap_reason,
        },

        "note": "Only add missing skills if you actually have hands-on experience. Do not fake skills.",
    }
