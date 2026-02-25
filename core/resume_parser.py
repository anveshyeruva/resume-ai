import re
from typing import List, Set, Dict
from core.jd_parser import SKILL_WHITELIST, _norm

ALIASES: Dict[str, List[str]] = {
    "cicd": ["ci/cd", "ci cd", "pipelines", "pipeline", "continuous integration", "continuous delivery"],
    "aws": ["amazon web services"],
    "kubernetes": ["k8s"],
    "cloudformation": ["cfn"],
    "opentofu": ["open tofu"],
    "privatelink": ["private link"],
    "vpc peering": ["peering"],
    "vpn": ["site to site vpn", "client vpn"],
}

def extract_resume_skills(resume_text: str) -> List[str]:
    raw = resume_text.lower()
    text = _norm(raw)

    found: Set[str] = set()

    # Direct whitelist match (supports multi-word like "vpc peering")
    for skill in SKILL_WHITELIST:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text):
            found.add(skill)

    # Alias match
    for canonical, alias_list in ALIASES.items():
        for a in alias_list:
            ap = r"\b" + re.escape(_norm(a)) + r"\b"
            if re.search(ap, text):
                found.add(canonical)

    # Token match for things like EC2, EKS, etc
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\+\.\-]{1,}", raw)
    for t in tokens:
        tt = _norm(t)
        if tt in SKILL_WHITELIST:
            found.add(tt)

    return sorted(found)
