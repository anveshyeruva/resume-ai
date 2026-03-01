import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

SECTION_ALIASES = {
    "responsibilities": {"essential responsibilities", "responsibilities", "what you will do", "key responsibilities"},
    "desired": {"desired experience", "requirements", "minimum qualifications", "must have", "you know you’re the right fit if"},
    "preferred": {"preferred experience", "preferred qualifications", "nice to have", "bonus"},
    "required_skills": {"required skills", "required skills & abilities", "skills & abilities", "skills"},
}

# Expanded whitelist so we can detect JD-specific tooling (GitOps/Argo/Flux/Bazel/CircleCI/etc.)
SKILL_WHITELIST = {
    # Cloud platforms
    "aws","azure","gcp",

    # AWS services
    "ec2","ecs","eks","lambda","s3","rds","dynamodb",

    # Infra + security
    "vpc","subnet","vpn","vpc peering","privatelink","iam","kms","route 53","cloudwatch","cloudtrail",

    # IaC
    "terraform","opentofu","pulumi","cloudformation","iac","infrastructure as code",

    # Containers
    "docker","kubernetes","helm","containers",

    # CI/CD + build
    "cicd","ci","cd","jenkins","github actions","gitlab","azure devops",
    "circleci","bazel",

    # GitOps
    "gitops","argocd","fluxcd",

    # Observability / ops
    "prometheus","grafana","datadog","splunk","apm","metrics","dashboards","alarms","incident response",

    # Languages
    "python","go","ruby","java",

    # General OS
    "linux","unix","windows",
}

_STOPWORDS = {
    "and","or","the","a","an","to","of","in","for","with","on","as","at","by","from",
    "you","we","our","your","will","work","team","teams","experience","knowledge",
    "ability","including","preferred","required","responsibilities","skills","tools",
    "role","candidate","engineer","engineering","software","development","platform",
}

def _norm(text: str) -> str:
    text = text.lower()
    text = text.replace("ci/cd", "cicd")
    text = text.replace("ci cd", "cicd")
    text = text.replace("github-actions", "github actions")
    text = text.replace("argo cd", "argocd")
    text = text.replace("flux cd", "fluxcd")
    text = text.replace("git ops", "gitops")
    text = re.sub(r"[^a-z0-9\+\#\.\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

@dataclass
class JobRequirements:
    responsibilities: List[str]
    required_skills: List[str]
    preferred_skills: List[str]
    keywords: List[str]   # NEW: compatibility with existing code

def _extract_section_lines(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    out = []
    i = start_idx
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # stop if looks like another header
        if line.endswith(":") and len(line) < 60:
            break
        out.append(line)
        i += 1
    return out, i

def _parse_sections(text: str) -> Dict[str, List[str]]:
    lines = [ln.strip() for ln in text.splitlines()]
    sections: Dict[str, List[str]] = {
        "responsibilities": [],
        "desired": [],
        "preferred": [],
        "required_skills": [],
    }

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        low = line.lower().rstrip(":").strip()

        key = None
        if low in SECTION_ALIASES["responsibilities"]:
            key = "responsibilities"
        elif low in SECTION_ALIASES["desired"]:
            key = "desired"
        elif low in SECTION_ALIASES["preferred"]:
            key = "preferred"
        elif low in SECTION_ALIASES["required_skills"]:
            key = "required_skills"

        if key:
            i += 1
            block, i = _extract_section_lines(lines, i)
            sections[key].extend(block)
            continue

        i += 1

    return sections

def _extract_skills(text: str) -> List[str]:
    t = _norm(text)
    found = set()

    multi = sorted([s for s in SKILL_WHITELIST if " " in s], key=len, reverse=True)
    for s in multi:
        if s in t:
            found.add(s)

    tokens = set(t.split())
    for s in SKILL_WHITELIST:
        if " " in s:
            continue
        if s in tokens:
            found.add(s)

    canon_map = {
        "containers": "docker",
        "infrastructure as code": "iac",
    }
    normalized = set(canon_map.get(s, s) for s in found)
    return sorted(normalized)

def _keywords_from_text(text: str, limit: int = 30) -> List[str]:
    """
    Lightweight keyword extraction for compatibility/UI. Not used for scoring.
    """
    t = _norm(text)
    toks = [x for x in t.split() if x not in _STOPWORDS and len(x) >= 3]
    freq: Dict[str, int] = {}
    for x in toks:
        freq[x] = freq.get(x, 0) + 1
    # most frequent tokens
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in top[:limit]]

def parse_job_description(text: str) -> JobRequirements:
    sections = _parse_sections(text)

    responsibilities = []
    for ln in sections["responsibilities"]:
        ln = re.sub(r"^\s*[-•*]\s+", "", ln).strip()
        ln = re.sub(r"^\s*\d+[.)]\s+", "", ln).strip()
        if ln and len(ln) >= 8:
            responsibilities.append(ln)

    req_text = "\n".join(sections["desired"] + sections["required_skills"])
    pref_text = "\n".join(sections["preferred"])

    required_skills = _extract_skills(req_text)
    preferred_skills = _extract_skills(pref_text)

    if not required_skills:
        required_skills = _extract_skills(text)

    # Keywords: prefer skills first, then fill with frequent tokens
    skills_first = list(dict.fromkeys(required_skills + preferred_skills))  # preserve order
    extras = _keywords_from_text(text, limit=60)
    keywords = []
    for k in skills_first + extras:
        if k not in keywords:
            keywords.append(k)
        if len(keywords) >= 30:
            break

    return JobRequirements(
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        keywords=keywords,
    )

def to_dict(req: JobRequirements) -> Dict:
    return asdict(req)
