from typing import Dict, List
from core.jd_parser import JobRequirements
from core.resume_parser import extract_resume_skills

def build_tailored_skills_section(req: JobRequirements, resume_text: str) -> Dict:
    resume_skills = set(extract_resume_skills(resume_text))

    must = [s for s in req.required_skills if s in resume_skills]
    nice = [s for s in req.preferred_skills if s in resume_skills]

    # Keep order: must first, then nice-to-have
    ordered = []
    for s in must + nice:
        if s not in ordered:
            ordered.append(s)

    # Simple grouping for display
    return {
        "skills_matched_to_jd": ordered,
        "note": "These are skills detected in your resume that match the JD. No new skills added."
    }

def suggest_bullet_enhancements(req: JobRequirements, resume_text: str) -> List[str]:
    # Lightweight recommendations (no rewriting yet)
    resume_skills = set(extract_resume_skills(resume_text))
    jd_skills_present = sorted(set(req.required_skills + req.preferred_skills) & resume_skills)

    suggestions = []
    if "cloudformation" in jd_skills_present and "CloudFormation" not in resume_text:
        suggestions.append("Consider adding CloudFormation into one experience bullet where it is truthful (you already list it under Tools).")
    if "lambda" in req.preferred_skills and "lambda" in resume_skills and "Lambda" not in resume_text:
        suggestions.append("If you used Lambda, add a bullet mentioning a Lambda-based workflow. If not, do not add.")
    if "vpc peering" in req.preferred_skills and "vpc peering" not in resume_skills:
        suggestions.append("JD mentions VPC peering. Only add if you have hands-on experience; otherwise ignore.")
    if "vpn" in req.preferred_skills and "vpn" not in resume_skills:
        suggestions.append("JD mentions VPN connectivity. Only add if you have configured site-to-site or client VPN; otherwise ignore.")

    # General recommendations
    suggestions.append("Mirror the JD language in bullets using skills you already have, without changing facts (example: 'deployment validation', 'troubleshooting', 'documentation').")
    suggestions.append("If applying anyway, be ready to explain Java exposure honestly. If no Java, this role may be a low-fit.")
    return suggestions
