"""Assemble the system and user prompts for the Gemini grading call.

Supports both whole-rubric and per-criterion evaluation (#12).
"""

import json
import logging
from typing import Any

log = logging.getLogger(__name__)


# ── Strict evidence-based grading rules (#5, #11) ──────────────────────────
_GRADING_RULES = """\
**Grading rules — strict evidence-based evaluation:**
1. Evaluate from the **lowest band (E) upward**. Award the highest band ONLY when the student's work clearly demonstrates ALL descriptors for that band.
2. If evidence for any descriptor within a band is missing, that band is NOT achieved — fall back to the highest band whose descriptors are fully satisfied.
3. Do NOT infer student intent. Only evaluate explicit statements present in the student's submission.
4. Evaluation must be based on **reasoning quality and explicit evidence**. Essay length alone must NOT influence grading. Ignore filler or repeated statements (#11).
5. Do NOT include generic praise. All feedback must be evidence-based.
6. For each criterion the feedback MUST:
   a. Cite **direct evidence** (quote or paraphrase) from the student's text.
   b. Explain **why the awarded band was chosen** with reference to the band descriptors.
   c. Explain **why the next higher band was NOT achieved**.
   d. Provide **actionable improvement advice** specific to the criterion.
7. Scores must be integers. The overall score must equal the sum of all criterion scores.
8. The band must be one of: A, B, C, D, E.
9. Each feedback field must contain at least 25 words of substantive analysis."""


def build_system_prompt(subject: str, assessment_type: str, technique: str) -> str:
    """Build system prompt for whole-rubric evaluation."""
    return f"""You are an expert QCAA (Queensland Curriculum & Assessment Authority) assessment marker for **{subject}** — **{assessment_type}: {technique}**.

Your task is to grade a student's assignment strictly against the official ISMG (Instrument-Specific Marking Guide) provided below.

{_GRADING_RULES}

**Output format:** Respond ONLY with valid JSON matching this exact schema — no markdown, no extra text:
{{
  "rubric_scores": [
    {{
      "criterion": "<criterion name>",
      "score": <integer>,
      "max_score": <integer>,
      "band": "<A|B|C|D|E>",
      "feedback": "<detailed feedback paragraph — min 25 words>",
      "improvement": "<specific improvement suggestions>"
    }}
  ],
  "overall_score": <integer — sum of all scores>,
  "max_overall_score": <integer — sum of all max_scores>,
  "feedback": "<overall summary paragraph>"
}}"""


def build_criterion_system_prompt(
    subject: str,
    assessment_type: str,
    technique: str,
    criterion_data: dict,
    mark_allocation_entry: dict | None = None,
) -> str:
    """Build a system prompt scoped to a SINGLE criterion (#12).

    Isolating criteria prevents strong performance in one criterion from
    inflating scores in another.
    """
    crit_name = criterion_data.get("criterion", "Unknown")

    # Format band descriptors for this criterion
    bands_text = ""
    for band in criterion_data.get("bands", []):
        marks = band.get("marks", "?")
        descriptors = band.get("descriptors", [])
        desc_text = "; ".join(descriptors) if descriptors else "—"
        bands_text += f"- **Marks {marks}:** {desc_text}\n"

    max_marks = ""
    if mark_allocation_entry:
        max_marks = f"\nMark allocation: {mark_allocation_entry.get('marks', '?')} marks (Assessment Objectives: {mark_allocation_entry.get('objectives', '—')})"

    return f"""You are an expert QCAA assessment marker for **{subject}** — **{assessment_type}: {technique}**.

You are evaluating ONLY the criterion **"{crit_name}"**.{max_marks}

### Band Descriptors for {crit_name}
{bands_text}

{_GRADING_RULES}

**Output format:** Respond ONLY with valid JSON — no markdown, no extra text.
Keep feedback between 25 and 80 words to avoid truncation.
{{
  "criterion": "{crit_name}",
  "score": <integer>,
  "max_score": <integer>,
  "band": "<A|B|C|D|E>",
  "feedback": "<detailed feedback paragraph — 25-80 words>",
  "improvement": "<specific improvement suggestions>",
  "evidence_quotes": ["<exact quote from student text>", ...],
  "band_analysis": {{
    "E": "<why band E descriptors are/aren't met — 1 sentence>",
    "D": "<why band D descriptors are/aren't met — 1 sentence>",
    "C": "<why band C descriptors are/aren't met — 1 sentence>",
    "B": "<why band B descriptors are/aren't met — 1 sentence>",
    "A": "<why band A descriptors are/aren't met — 1 sentence>"
  }}
}}

IMPORTANT:
- "evidence_quotes" must contain 2-5 EXACT verbatim excerpts copied from the student submission that justify the score. Each quote must appear word-for-word in the student's text.
- "band_analysis" must evaluate EVERY band (E through A) explaining whether descriptors are met, even if the band was not awarded."""


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


def build_criterion_user_prompt(
    rag_chunks: list[dict],
    assignment_text: str,
) -> str:
    """Build a minimal user prompt for per-criterion evaluation (#12)."""
    parts: list[str] = []

    if rag_chunks:
        parts.append("## Relevant Syllabus Context\n")
        for chunk in rag_chunks:
            section = chunk.get("section", "")
            content = chunk.get("content", "")
            sim = chunk.get("similarity", 0)
            parts.append(f"### [{section}] (relevance: {sim:.2f})")
            if len(content) > 1500:
                content = content[:1500] + "…"
            parts.append(content)
            parts.append("")

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
