# Resume AI Builder (Streamlit, Local-first)

A local-first Streamlit app that analyzes a Job Description against a base resume, builds a requirements scorecard + gap analysis, computes a match percentage, and exports a tailored DOCX. Optional AI rewriting supports **Local (Ollama)** and **Cloud (OpenAI)**.

---

## What you get

- JD parsing (responsibilities + keywords)
- Requirements scorecard (Must-have and Nice-to-have)
- Gap analysis (present vs missing, with confidence buckets)
- **Match %** (weighted)
- Tailoring suggestions
- DOCX export (with caching)
- AI modes: Off, Local, Cloud

---

## Requirements

- Python **3.10+** (recommended 3.11+)
- macOS, Linux, or Windows
- (Optional) Ollama for local AI
- (Optional) OpenAI API key for cloud AI

---

## Setup (macOS / Linux)

### 1) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
