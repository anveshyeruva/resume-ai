# AI Resume Builder Requirements

## Goal
Generate a tailored resume in Anvesh's specified format using a job description or job URL, with zero cost and local-first operation.

## Functional
- Accept JD input as pasted text (must).
- Accept job URL and fetch JD text when possible (nice-to-have; LinkedIn not supported).
- Accept base resume text (master resume).
- Parse JD into: role title, responsibilities, required skills, preferred skills, keywords.
- Generate a resume that uses ONLY facts present in the base resume.
- Enforce formatting rules:
  - No slash characters anywhere.
  - Explainable bullets.
  - Required section order.
  - Environment line per experience entry.
- Export DOCX (must).
- Export PDF (optional).

## Non-functional
- Zero cost: no paid APIs, no cloud hosting required.
- Local-first: works entirely on the laptop.
- Reproducible: single command to run.
- Observable: clear logs and errors.
- Testable: unit tests for parser and validator.

## Security
- No uploading resume content to external services.
- Model calls must be local (Ollama) when AI is enabled.

## Ops
- Streamlit app for UI.
- Config-driven resume format rules.
- Support "parse-only" mode without AI generation.
