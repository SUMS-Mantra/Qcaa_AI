"""Assemble the system and user prompts for the Gemini grading call."""

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


def build_system_prompt(subject: str, assessment_type: str, technique: str) -> str:
    return f"""You are an expert QCAA (Queensland Curriculum & Assessment Authority) assessment marker for **{subject}** — **{assessment_type}: {technique}**.

Your task is to grade a student's assignment strictly against the official ISMG (Instrument-Specific Marking Guide) provided below.

**Grading rules:**
1. For EACH criterion in the ISMG, assign an integer score within the mark range shown.
2. Determine which band (A–E) the student's work falls into by matching their response against the band descriptors.
3. Write a **detailed feedback paragraph** (at least 3 sentences) for each criterion that:
   - Cites specific evidence from the student's work
   - Explains why the work falls into the assigned band
   - States what the student did well
4. Write **specific improvement suggestions** explaining exactly what the student should do differently to reach the next band up.
5. Write an **overall summary** (3–5 sentences) covering the submission's strengths and key areas for improvement.
6. Scores must be integers. The overall score must equal the sum of all criterion scores.

**Output format:** Respond ONLY with valid JSON matching this exact schema — no markdown, no extra text:
{{
  "rubric_scores": [
    {{
      "criterion": "<criterion name>",
      "score": <integer>,
      "max_score": <integer>,
      "band": "<A|B|C|D|E>",
      "feedback": "<detailed feedback paragraph>",
      "improvement": "<specific improvement suggestions>"
    }}
  ],
  "overall_score": <integer — sum of all scores>,
  "max_overall_score": <integer — sum of all max_scores>,
  "feedback": "<overall summary paragraph>"
}}"""


def build_user_prompt(
    context: dict[str, Any],
    rag_chunks: list[dict],
    assignment_text: str,
) -> str:
    """Build the user message with all context + student text."""
    parts: list[str] = []

    assessment = context.get("assessment", {})

    # ── ISMG criteria + band descriptors ──
    ismg = assessment.get("ismg", [])
    if ismg:
        parts.append("## ISMG — Instrument-Specific Marking Guide\n")
        for criterion_data in ismg:
            crit_name = criterion_data.get("criterion", "Unknown")
            parts.append(f"### Criterion: {crit_name}")
            for band in criterion_data.get("bands", []):
                marks = band.get("marks", "?")
                descriptors = band.get("descriptors", [])
                desc_text = "; ".join(descriptors) if descriptors else "—"
                parts.append(f"- **Marks {marks}:** {desc_text}")
            parts.append("")

    # ── Mark allocations ──
    mark_alloc = assessment.get("mark_allocation", {})
    if mark_alloc.get("criteria"):
        parts.append("## Mark Allocation\n")
        for ma in mark_alloc["criteria"]:
            parts.append(
                f"- **{ma['criterion']}**: {ma['marks']} marks "
                f"(Assessment Objectives: {ma.get('objectives', '—')})"
            )
        parts.append(f"- **Total: {mark_alloc.get('total_marks', '?')} marks**\n")

    # ── Assessment conditions ──
    conditions = assessment.get("conditions", {})
    technique = assessment.get("technique", "")
    if technique:
        parts.append(f"## Assessment: {technique}\n")
    if conditions:
        parts.append("## Conditions\n")
        for k, v in conditions.items():
            parts.append(f"- {k}: {v}")
        parts.append("")

    # ── RAG syllabus context ──
    if rag_chunks:
        parts.append("## Relevant Syllabus Context\n")
        for chunk in rag_chunks:
            section = chunk.get("section", "")
            content = chunk.get("content", "")
            sim = chunk.get("similarity", 0)
            parts.append(f"### [{section}] (relevance: {sim:.2f})")
            # Truncate very long chunks
            if len(content) > 1500:
                content = content[:1500] + "…"
            parts.append(content)
            parts.append("")

    # ── Student submission ──
    parts.append("## Student Submission\n")
    parts.append("--- BEGIN STUDENT WORK ---")
    parts.append(assignment_text)
    parts.append("--- END STUDENT WORK ---")

    return "\n".join(parts)


def build_messages(
    context: dict[str, Any],
    rag_chunks: list[dict],
    assignment_text: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) ready for the LLM call."""
    assessment = context.get("assessment", {})
    subject = context.get("subject", "Unknown")
    assessment_type = context.get("assessment_type", "Unknown")
    technique = assessment.get("technique", assessment_type)

    system = build_system_prompt(subject, assessment_type, technique)
    user = build_user_prompt(context, rag_chunks, assignment_text)

    log.info(
        "Prompt built: system=%d chars, user=%d chars",
        len(system),
        len(user),
    )
    return system, user
