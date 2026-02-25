from typing import Dict, List
from core.jd_parser import JobRequirements

CATEGORY_MAP = {
    "Cloud": {"aws", "azure", "gcp"},
    "AWS Services": {"ec2", "ecs", "eks", "rds", "lambda", "s3"},
    "Networking": {"vpc", "subnet", "vpn", "vpc peering", "privatelink"},
    "IaC": {"terraform", "opentofu", "pulumi", "cloudformation"},
    "Containers": {"docker", "kubernetes"},
    "CI CD": {"cicd", "ci", "cd", "jenkins", "github", "gitlab"},
    "OS": {"linux", "unix"},
    "Build": {"maven", "gradle"},
    "Languages": {"java", "python"},
}

def _group(skills: List[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {k: [] for k in CATEGORY_MAP}
    other: List[str] = []
    for s in skills:
        placed = False
        for cat, bag in CATEGORY_MAP.items():
            if s in bag:
                grouped[cat].append(s)
                placed = True
                break
        if not placed:
            other.append(s)

    # remove empty categories
    grouped = {k: v for k, v in grouped.items() if v}
    if other:
        grouped["Other"] = sorted(other)
    # sort each category
    for k in list(grouped.keys()):
        grouped[k] = sorted(set(grouped[k]))
    return grouped

def make_scorecard(req: JobRequirements) -> Dict:
    must = sorted(set(req.required_skills))
    nice = sorted(set(req.preferred_skills))

    return {
        "must_have": must,
        "nice_to_have": nice,
        "must_grouped": _group(must),
        "nice_grouped": _group(nice),
        "responsibilities": req.responsibilities,
        "keywords_top": req.keywords[:30],
    }
