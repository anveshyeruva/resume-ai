import re
from typing import List, Dict
from core.jd_parser import SKILL_WHITELIST, _norm

ALIASES: Dict[str, List[str]] = {
    "cicd": ["ci/cd", "ci cd", "pipelines", "pipeline", "continuous integration", "continuous delivery"],
    "aws": ["amazon web services"],
    "kubernetes": ["k8s"],
    "cloudformation": ["cfn"],
    "opentofu": ["open tofu"],
    "privatelink": ["private link"],
    "vpc peering": ["peering"],
    "vpn": ["site to site vpn", "site-to-site vpn", "client vpn"],
    "github actions": ["github-actions", "actions (github)"],
    "azure devops": ["ado", "azure devops pipelines"],
    "argocd": ["argo cd", "argo-cd"],
    "fluxcd": ["flux cd", "flux-cd"],
    "gitops": ["git ops", "git-ops"],
    "circleci": ["circle ci", "circle-ci"],
}

def extract_resume_skills(resume_text: str) -> List[str]:
    raw = (resume_text or "").lower()
    text = _norm(raw)

    # expand aliases into canonical mentions
    expanded = text
    for canon, variants in ALIASES.items():
        for v in variants:
            if v in expanded:
                expanded += f" {canon}"

    found = set()

    # multi-word first
    multi = sorted([s for s in SKILL_WHITELIST if " " in s], key=len, reverse=True)
    for s in multi:
        if s in expanded:
            found.add(s)

    tokens = set(expanded.split())
    for s in SKILL_WHITELIST:
        if " " in s:
            continue
        if s in tokens:
            found.add(s)

    # normalize a few common overlaps
    canon_map = {
        "containers": "docker",
        "infrastructure as code": "iac",
        "iac": "iac",
    }
    normalized = set(canon_map.get(s, s) for s in found)

    return sorted(normalized)
