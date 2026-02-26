# Resume AI (Local-First)

A local-first Streamlit app that helps you tailor your resume to a job description by:
- Parsing responsibilities and requirements from the JD
- Building a requirements scorecard (must-have vs nice-to-have)
- Highlighting gaps and top keywords
- Exporting a DOCX scorecard for quick review and sharing

> AI rewriting is optional and can be added later (e.g., Ollama). The core workflow runs fully locally.

---

## Features

- **JD parser:** Extracts responsibilities, must-haves, and nice-to-haves from job descriptions
- **Requirements scorecard:** Grouped chips and match coverage summary
- **Gap analysis:** Missing keywords and requirements surfaced clearly
- **Sponsorship signals:** Detects explicit authorization language and contracting constraints (W2 vs C2C)
- **DOCX export:** Generates a downloadable scorecard document
- **Local-first:** No cloud dependency required for the baseline flow

---

## Tech Stack

- Python
- Streamlit
- python-docx (DOCX export)

---

## Project Structure
