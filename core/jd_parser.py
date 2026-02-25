import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

SECTION_ALIASES = {
    "responsibilities": {"essential responsibilities", "responsibilities", "what you will do", "key responsibilities"},
    "desired": {"desired experience", "requirements", "minimum qualifications", "must have"},
    "preferred": {"preferred experience", "preferred qualifications", "nice to have", "bonus"},
    "required_skills": {"required skills", "required skills & abilities", "skills & abilities", "skills"},
}

SKILL_WHITELIST = {
    "aws","azure","gcp","ec2","ecs","eks","rds","lambda","s3","vpc","cloudformation",
    "terraform","opentofu","pulumi","docker","kubernetes","linux","unix",
    "ci","cd","cicd","jenkins","github","gitlab","maven","gradle","java","python",
    "privatelink","vpn","vpc peering","subnet","iam"
}

@dataclass
class JobRequirements:
    title: str
    company: str
    location: str
    keywords: List[str]
    responsibilities: List[str]
    required_skills: List[str]
    preferred_skills: List[str]

def _clean_lines(text: str) -> List[str]:
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    return [l for l in lines if l]

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9\s&/+-]", "", s.lower()).strip()

def extract_keywords(text: str, top_n: int = 40) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\+\.\-]{1,}", text)
    stop = set("""
        and or the with for to of in a an on as is are be from by this that will
        you we our your their they them it its
    """.split())
    freq: Dict[str, int] = {}
    for t in tokens:
        tl = t.lower()
        if tl in stop or len(tl) < 3:
            continue
        freq[tl] = freq.get(tl, 0) + 1
    return [k for k, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]

def _find_sections(lines: List[str]) -> Dict[str, Tuple[int, int]]:
    """
    Returns map: section_name -> (start_index_inclusive, end_index_exclusive)
    """
    headers = []
    for i, line in enumerate(lines):
        n = _norm(line)
        for sec, aliases in SECTION_ALIASES.items():
            if n in aliases:
                headers.append((i, sec))
                break

    # sort and build ranges
    headers.sort(key=lambda x: x[0])
    ranges: Dict[str, Tuple[int, int]] = {}
    for idx, (start, sec) in enumerate(headers):
        end = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        ranges[sec] = (start + 1, end)  # content begins after header line
    return ranges

def _as_items(block_lines: List[str]) -> List[str]:
    items = []
    for l in block_lines:
        # stop if we hit an empty line (already removed empties) or another obvious header-style line
        if len(l) <= 2:
            continue
        # remove bullet markers if present
        l = re.sub(r"^[•\-\*]\s*", "", l).strip()
        # ignore pure section-like lines
        if _norm(l) in {a for s in SECTION_ALIASES.values() for a in s}:
            continue
        items.append(l)
    return items

def _extract_skills_from_text(text: str) -> List[str]:
    """
    Pulls likely skills from:
    - parentheses lists: (EC2, ECS, ...)
    - slash lists: Terraform/OpenTofu/Pulumi
    - known tokens
    """
    found = set()

    # Parentheses groups
    for grp in re.findall(r"\(([^)]+)\)", text):
        parts = re.split(r"[,\|/]", grp)
        for p in parts:
            t = _norm(p)
            if not t:
                continue
            found.add(t)

    # Slash or comma separated terms across the whole text
    rough = re.split(r"[,\n]", text)
    for chunk in rough:
        for p in re.split(r"[\/\|]", chunk):
            t = _norm(p)
            if not t:
                continue
            # keep short known terms
            if t in SKILL_WHITELIST:
                found.add(t)

    # token scan
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\+\.\-]{1,}", text.lower())
    for t in tokens:
        tt = _norm(t)
        if tt in SKILL_WHITELIST:
            found.add(tt)

    # normalize some common variants
    normalize_map = {
        "ci cd": "cicd",
        "ci/cd": "cicd",
        "ci": "ci",
        "cd": "cd",
    }
    normalized = set()
    for f in found:
        normalized.add(normalize_map.get(f, f))

    # Return stable ordering
    return sorted(normalized)

def _guess_title(lines: List[str]) -> str:
    # Look for a line that looks like a job title
    for l in lines[:15]:
        low = l.lower()
        if any(w in low for w in ["devops", "site reliability", "sre", "platform engineer", "cloud engineer", "infrastructure engineer"]):
            if len(l) <= 90:
                return l
    # Otherwise blank (better than wrong)
    return ""

def parse_job_description(jd_text: str) -> JobRequirements:
    lines = _clean_lines(jd_text)
    title = _guess_title(lines)
    company = ""
    location = ""

    sections = _find_sections(lines)

    responsibilities: List[str] = []
    if "responsibilities" in sections:
        s, e = sections["responsibilities"]
        responsibilities = _as_items(lines[s:e])

    # Required skills: combine "required_skills" section and "desired" section
    required_text_parts = []
    if "required_skills" in sections:
        s, e = sections["required_skills"]
        required_text_parts.append("\n".join(lines[s:e]))
    if "desired" in sections:
        s, e = sections["desired"]
        required_text_parts.append("\n".join(lines[s:e]))
    required_text = "\n".join(required_text_parts)

    preferred_text = ""
    if "preferred" in sections:
        s, e = sections["preferred"]
        preferred_text = "\n".join(lines[s:e])

    required_skills = _extract_skills_from_text(required_text)
    preferred_skills = _extract_skills_from_text(preferred_text)

    # keywords from whole JD
    keywords = extract_keywords(jd_text)

    return JobRequirements(
        title=title,
        company=company,
        location=location,
        keywords=keywords,
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
    )

def to_dict(req: JobRequirements) -> Dict:
    return asdict(req)
