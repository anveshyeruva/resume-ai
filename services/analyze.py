import re
from collections import defaultdict

from core.jd_parser import parse_job_description, to_dict
from core.scorecard import make_scorecard
from core.gap_analysis import analyze_gaps
from core.draft_tailor import build_tailored_skills_section, suggest_bullet_enhancements
from ui.sponsorship import analyze_sponsorship
from logger import get_logger

log = get_logger("services.analyze")

# Never treat these as skills/requirements
CONSTRAINT_TERMS = {
    "c2c","corp to corp","corp-to-corp","w2","1099","no c2c","no corp to corp","no sponsorship",
    "authorized to work","work authorization","citizen","citizenship","green card","us person",
}

SEEDED_TECH = [
    "aws","azure","gcp","vmware","vmc","vcdr","forgerock",
    "cloudformation","terraform","infrastructure as code","iac",
    "kubernetes","docker","ecs","eks","fargate",
    "vpc","iam","cloudwatch","cloudtrail","kms","route 53",
    "monitoring","logging","observability",
    "backup","recovery","security",
    "migration","on-prem","cloud-native",
    "linux","windows",
    "agile",
]

CAPABILITY_TERMS = {
    "monitoring","logging","observability","backup","recovery","security",
    "migration","on-prem","cloud-native","infrastructure as code","iac",
    "linux","windows"
}

# Aliases: treat these as equivalents when matching in resume text
ALIASES = {
    "iac": ["terraform", "cloudformation", "infrastructure as code", "iac"],
    "infrastructure as code": ["terraform", "cloudformation", "infrastructure as code", "iac"],
    "migration": ["migrate", "migration", "modernize", "on-prem to cloud", "cloud migration"],
    "on-prem": ["on-prem", "on premise", "onprem", "data center", "datacenter"],
    "cloud-native": ["cloud-native", "cloud native", "kubernetes", "container", "microservices"],
    "backup": ["backup", "backups", "snapshot", "snapshots", "restore", "restores"],
    "recovery": ["recovery", "restore", "restores", "dr", "disaster recovery", "failover"],
    "monitoring": ["monitoring", "cloudwatch", "dashboard", "dashboards", "alerts", "observability"],
    "logging": ["logging", "logs", "cloudtrail", "log-driven"],
    "security": ["security", "iam", "kms", "least privilege", "encryption"],
}

_STOP = {
    "and","or","the","a","an","to","of","in","for","with","on","as","is","are","be","this","that",
    "will","you","your","our","we","they","their","role","team","teams","work","experience",
    "about","apply","now","future","both","must","required","minimum","preferred","plus",
    "engineer","engineering","administrator","admin","cloud","systems","system",
    "excellent","communication","collaborate","collaboration","training","educate",
    "knowledge","understanding","abilities","ability","related","support","perform",
    "create","maintain","documentation","processes","problem","problem-solving",
    "us","u.s","usa","united","states",
    "bachelor","degree","computer","science","information","technology","it","proficiency","exposure","familiarity","bring",
    "c2c","w2","1099",
    "design","build","deploy","participate","phases","lifecycle","lead","educate","monitor","investigate","resolve","assist","collaborate","advance","legacy",
    "emerging","audit","audits","data","checks","advanced","internal","offer","offers","escalations","contract","hire","madison","insurance","code","scalability","performance"
}

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[\u2022•\t]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(".,:;()[]{}")

def _contains_constraint(term: str) -> bool:
    t = _norm(term)
    if t in CONSTRAINT_TERMS:
        return True
    if "c2c" in t or "w2" in t or "corp" in t:
        return True
    return False

def extract_responsibilities(jd_text: str, max_items: int = 12) -> list:
    text = jd_text or ""
    lines = [ln.rstrip() for ln in text.splitlines()]

    heading_re = re.compile(r"^\s*(what you[’']?ll do|responsibilities|duties|what you will do)\s*$", re.I)
    next_heading_re = re.compile(
        r"^\s*(summary|what you[’']?ll bring|requirements|qualifications|what you’ll bring|what you'll bring)\s*$",
        re.I,
    )

    start_idx = None
    for i, ln in enumerate(lines):
        if heading_re.match(ln.strip()):
            start_idx = i + 1
            break

    if start_idx is None:
        return []

    bullets = []
    for j in range(start_idx, len(lines)):
        ln = lines[j].strip()
        if not ln:
            continue

        if next_heading_re.match(ln) and len(bullets) > 0:
            break

        is_bullet = ln.startswith(("-", "*", "•")) or re.match(r"^\d+[\.\)]\s+", ln)
        if is_bullet:
            ln = re.sub(r"^(\-|\*|•|\d+[\.\)])\s*", "", ln).strip()

        if len(ln) >= 10 and (is_bullet or ln.endswith(".") or len(bullets) < 3):
            bullets.append(ln)

        if len(bullets) >= max_items:
            break

    seen = set()
    out = []
    for b in bullets:
        k = _norm(b)
        if k and k not in seen:
            seen.add(k)
            out.append(b)
    return out

def _extract_candidate_terms(jd_text: str):
    text = jd_text or ""
    low = text.lower()
    found = set()

    for t in SEEDED_TECH:
        if t in low:
            found.add(t)

    phrase_patterns = [
        r"on[-\s]?prem(?:ise)?\s+to\s+cloud",
        r"cloud[-\s]?native\s+architectures?",
        r"monitoring\s+and\s+logging",
        r"backup\s+and\s+recovery",
        r"infrastructure\s+as\s+code",
        r"root\s+cause\s+analysis",
        r"cloud\s+migration",
        r"cost[-\s]?efficien(t|cy)",
    ]
    for pat in phrase_patterns:
        m = re.search(pat, low)
        if m:
            found.add(_norm(m.group(0)))

    for m in re.finditer(r"\b[A-Z]{2,}\b", text):
        term = m.group(0).strip()
        if term and len(term) <= 12:
            found.add(term.lower())


    # Title-case words are often noisy (e.g., "Design", "Lead", location names).
    # Keep only known tech proper nouns or tokens that "look technical" (digits, hyphen, plus).
    ALLOWED_PROPER_TECH = {
        "aws","azure","gcp","vmware","cloudformation","terraform","kubernetes","docker",
        "forgerock","vmc","vcdr","cloudwatch","cloudtrail","route 53","iam","kms",
    }
    for m in re.finditer(r"\b[A-Z][a-zA-Z0-9\-\+]{2,}\b", text):
        w = m.group(0).strip().lower()
        looks_techy = any(ch.isdigit() for ch in w) or ("-" in w) or ("+" in w)
        if w in ALLOWED_PROPER_TECH or looks_techy:
            found.add(w)

    cleaned = []
    for t in found:
        t = _norm(t)
        if not t or t in _STOP:
            continue
        if _contains_constraint(t):
            continue
        if len(t) <= 2 and t not in {"ai","ci"}:
            continue
        cleaned.append(t)

    seeded_present = [t for t in cleaned if t in SEEDED_TECH]
    other_terms = [t for t in cleaned if t not in SEEDED_TECH and t not in _STOP and not t.isdigit()]
    return sorted(set(seeded_present)) + sorted(set(other_terms))

def _fallback_scorecard(jd_text: str):
    text = jd_text or ""
    terms = _extract_candidate_terms(text)

    must_markers = ["must", "required", "minimum"]
    nice_markers = ["preferred", "plus", "a plus", "nice to have", "bonus"]

    must, nice = [], []

    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        ll = l.lower()

        line_terms = [t for t in terms if t in ll]
        if not line_terms:
            continue

        if any(m in ll for m in nice_markers):
            nice.extend(line_terms)
            continue
        if any(m in ll for m in must_markers):
            must.extend(line_terms)
            continue

    if not must:
        must = [t for t in terms if t in CAPABILITY_TERMS or t in {"aws","iac","infrastructure as code"}]

    for essential in ["aws","monitoring","logging","migration","security","backup","recovery","iac","infrastructure as code","on-prem","cloud-native"]:
        if essential in terms and essential not in must:
            must.append(essential)

    must = sorted(set([t for t in must if t not in _STOP and not _contains_constraint(t)]))[:30]
    nice = sorted(set([t for t in nice if t not in _STOP and not _contains_constraint(t) and t not in must]))[:30]

    def pretty(t: str) -> str:
        if t in {"aws","gcp"}: return t.upper()
        if t == "iam": return "IAM"
        if t == "kms": return "KMS"
        if t == "route 53": return "Route 53"
        if t == "cloudwatch": return "CloudWatch"
        if t == "cloudtrail": return "CloudTrail"
        if t in {"iac","infrastructure as code"}: return "IaC"
        if t == "cloudformation": return "CloudFormation"
        if t == "vmware": return "VMware"
        if t == "forgerock": return "ForgeRock"
        if t in {"vmc","vcdr"}: return t.upper()
        return t.title()

    def group(items):
        g = defaultdict(list)

        def add(bucket: str, value: str):
            if bucket not in g:
                g[bucket] = []
            if value not in g[bucket]:
                g[bucket].append(value)

        for t in items:
            tt = pretty(t)

            if t in {"aws","azure","gcp","vmware","vmc","vcdr"}:
                add("Cloud", tt)
            elif t in {"terraform","cloudformation","iac","infrastructure as code"}:
                add("IaC", tt)
            elif t in {"kubernetes","docker","ecs","eks","fargate"}:
                add("Containers", tt)
            elif t in {"monitoring","logging","observability","cloudwatch","cloudtrail","monitoring and logging"}:
                add("Observability", tt)
            elif t in {"security","kms","iam"}:
                add("Security", tt)
            elif t in {"migration","on-prem","cloud-native","cloud migration","on-prem to cloud","cloud-native architectures"}:
                add("Modernization", tt)
            elif t in {"backup","recovery","backup and recovery"}:
                add("Resilience", tt)
            elif t in {"linux","windows"}:
                add("Operating Systems", tt)
            elif t == "forgerock":
                add("Identity", tt)
            else:
                add("General", tt)

        return {k: v[:12] for k, v in g.items() if v}

    return {
        "must_grouped": group(must),
        "nice_grouped": group(nice),
        "keywords_top": terms[:35],
    }

def _fallback_gaps_from_scorecard(scorecard: dict, resume_text: str):
    resume_low = (resume_text or "").lower()

    def flatten(grouped):
        out = []
        for _, arr in (grouped or {}).items():
            if isinstance(arr, str):
                out.append(arr)
            else:
                out.extend(arr or [])
        return sorted(set([_norm(x) for x in out if x]))

    def is_present(term: str) -> bool:
        t = _norm(term)
        if not t or _contains_constraint(t):
            return False

        if t in resume_low:
            return True

        for alt in ALIASES.get(t, []):
            if alt and alt in resume_low:
                return True
        return False

    must = [t for t in flatten(scorecard.get("must_grouped")) if not _contains_constraint(t)]
    nice = [t for t in flatten(scorecard.get("nice_grouped")) if not _contains_constraint(t)]

    must_present = [t for t in must if is_present(t)]
    must_missing = [t for t in must if not is_present(t)]
    nice_present = [t for t in nice if is_present(t)]
    nice_missing = [t for t in nice if not is_present(t)]

    return {
        "must_present": must_present,
        "must_missing_high": must_missing,
        "must_missing_maybe": [],
        "nice_present": nice_present,
        "nice_missing_high": nice_missing,
        "nice_missing_maybe": [],
        "note": "Fallback gap analysis used (core scorecard quality was low).",
    }

def _core_scorecard_quality(scorecard: dict) -> int:
    def flatten(grouped):
        out = []
        for _, arr in (grouped or {}).items():
            if isinstance(arr, str):
                out.append(arr)
            else:
                out.extend(arr or [])
        return {_norm(x) for x in out if x}

    all_terms = flatten((scorecard or {}).get("must_grouped")) | flatten((scorecard or {}).get("nice_grouped"))
    return sum(1 for t in SEEDED_TECH if t in all_terms)

def _compute_matched_skills(keywords_top: list, resume_text: str) -> list:
    resume_low = (resume_text or "").lower()
    matched = []
    for t in (keywords_top or []):
        tt = _norm(t)
        if not tt or tt in _STOP or _contains_constraint(tt):
            continue
        if tt in resume_low:
            matched.append(tt)

    def rank(x):
        if x in SEEDED_TECH: return 0
        if x in CAPABILITY_TERMS: return 1
        return 2

    matched = sorted(set(matched), key=lambda x: (rank(x), x))
    return matched[:30]

def _filter_suggestions(suggestions: list, jd_text: str, resume_text: str) -> list:
    jd_low = (jd_text or "").lower()
    resume_low = (resume_text or "").lower()

    cleaned = []
    for s in (suggestions or []):
        if not s or not isinstance(s, str):
            continue
        sl = s.lower()

        # Hard-block any java mention unless JD/resume mentions java
        if "java" in sl and ("java" not in jd_low) and ("java" not in resume_low):
            continue

        cleaned.append(s)

    if not cleaned:
        cleaned = [
            "Mirror JD language in bullets using skills you already have (AWS, monitoring, logging, incident response, documentation).",
            "Emphasize on-prem to cloud migration support if you have any related project or production exposure.",
            "Call out cost-efficiency improvements (right-sizing, alert tuning, autoscaling) if you have done similar work.",
        ]
    return cleaned[:12]

def run_analysis(jd_text: str, base_resume: str) -> dict:
    log.info("Running analysis (jd_len=%s, resume_len=%s)", len(jd_text or ""), len(base_resume or ""))

    req = parse_job_description(jd_text)
    score = make_scorecard(req)
    gaps = analyze_gaps(req, base_resume)

    responsibilities = extract_responsibilities(jd_text)

    try:
        _ = build_tailored_skills_section(req, base_resume) or {}
    except Exception:
        pass

    try:
        suggestions = suggest_bullet_enhancements(req, base_resume) or []
    except Exception:
        suggestions = []

    core_quality = _core_scorecard_quality(score)
    if core_quality < 3:
        fb = _fallback_scorecard(jd_text)
        score = {
            **score,
            "must_grouped": fb["must_grouped"],
            "nice_grouped": fb["nice_grouped"],
            "keywords_top": fb["keywords_top"],
        }
        gaps = _fallback_gaps_from_scorecard(score, base_resume)

    matched_skills = _compute_matched_skills(score.get("keywords_top", []), base_resume)
    suggestions = _filter_suggestions(suggestions, jd_text, base_resume)

    return {
        "jd_text": jd_text,
        "req": to_dict(req),
        "keywords_top": score.get("keywords_top", []),
        "scorecard": score,
        "gaps": gaps,
        "responsibilities": responsibilities,
        "matched_skills": matched_skills,
        "suggestions": suggestions,
        "base_resume": base_resume,
        "sponsorship": analyze_sponsorship(jd_text),
    }