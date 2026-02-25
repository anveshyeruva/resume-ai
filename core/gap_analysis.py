from typing import Dict
from core.jd_parser import JobRequirements
from core.resume_parser import extract_resume_skills

# If you have Linux, Unix is usually implied in many DevOps contexts (mark as "maybe")
DERIVED_MAYBE = {
    "unix": ["linux"],
    "ci": ["cicd"],
    "cd": ["cicd"],
}

def analyze_gaps(req: JobRequirements, resume_text: str) -> Dict:
    resume_skills = set(extract_resume_skills(resume_text))

    must = set(req.required_skills)
    nice = set(req.preferred_skills)

    must_present = sorted(must & resume_skills)
    must_missing_raw = sorted(must - resume_skills)

    nice_present = sorted(nice & resume_skills)
    nice_missing_raw = sorted(nice - resume_skills)

    def split_missing(missing_list):
        missing_high = []
        missing_maybe = []
        for m in missing_list:
            implied_by = DERIVED_MAYBE.get(m, [])
            if any(x in resume_skills for x in implied_by):
                missing_maybe.append(m)
            else:
                missing_high.append(m)
        return missing_high, missing_maybe

    must_missing_high, must_missing_maybe = split_missing(must_missing_raw)
    nice_missing_high, nice_missing_maybe = split_missing(nice_missing_raw)

    return {
        "resume_skills_detected": sorted(resume_skills),
        "must_present": must_present,
        "must_missing_high": must_missing_high,
        "must_missing_maybe": must_missing_maybe,
        "nice_present": nice_present,
        "nice_missing_high": nice_missing_high,
        "nice_missing_maybe": nice_missing_maybe,
        "note": "Only add missing skills if you actually have hands-on experience. Do not fake skills."
    }
