"""FastAPI AI grading service — evaluates student work against QCAA rubrics.

Refactored for deterministic, strict, evidence-based grading.
Per-criterion evaluation prevents cross-criterion score inflation (#12).
"""

import hashlib
import json
import logging
import sys
import traceback

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from config import PORT, GEMINI_API_KEY, GEMINI_MODEL
from text_extractor import extract_text
from context_builder import build_context
from vector_search import search as vector_search, build_multi_section_query
from prompt_builder import (
    build_messages,
    build_criterion_system_prompt,
    build_criterion_user_prompt,
)
from llm_client import call_gemini
from response_parser import validate_and_normalise, validate_single_criterion, ValidationError

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

app = FastAPI(title="QCAA AI Grading Service", version="1.0.0")


# ── Helpers ─────────────────────────────────────────────────────────────────
def generate_seed(text: str) -> int:
    """Derive a deterministic seed from submission text via SHA-256 (#3).

    Identical submissions always produce the same seed, ensuring
    reproducible LLM outputs when combined with temperature=0.
    The Gemini API requires seed to be a signed INT32 (max 2_147_483_647).
    """
    hash_val = hashlib.sha256(text.encode()).hexdigest()
    return int(hash_val[:8], 16) & 0x7FFFFFFF


# ── Response models ─────────────────────────────────────────────────────────
class CriterionResult(BaseModel):
    criterion: str
    score: int
    max_score: int
    band: str = ""
    feedback: str = ""
    improvement: str = ""
    evidence_quotes: list[str] = []
    band_analysis: dict[str, str] = {}


class EvaluateResponse(BaseModel):
    rubric_scores: list[CriterionResult]
    overall_score: int
    max_overall_score: int
    feedback: str
    model_version: str
    assignment_text: str = ""


# ── Health check ────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model": GEMINI_MODEL}


def _call_with_retry(
    system_prompt: str,
    user_prompt: str,
    seed: int,
    validate_fn,
    validate_args: tuple = (),
    max_attempts: int = 2,
):
    """Call Gemini and validate; retry once with error hint on failure (#7).

    Parameters
    ----------
    system_prompt, user_prompt : str
        Prompts for the LLM.
    seed : int
        Deterministic seed.
    validate_fn : callable
        Validation function to call on the parsed result.
    validate_args : tuple
        Extra args to pass to validate_fn after the raw result.
    max_attempts : int
        Maximum number of attempts (default 2: initial + 1 retry).

    Returns
    -------
    dict
        Validated result.
    """
    current_user_prompt = user_prompt

    for attempt in range(max_attempts):
        try:
            raw_result = call_gemini(system_prompt, current_user_prompt, seed=seed)
        except ValueError as exc:
            # Malformed/truncated JSON from Gemini — retry with hint
            if attempt == max_attempts - 1:
                raise
            log.warning("Attempt %d JSON parse failed: %s — retrying", attempt + 1, exc)
            current_user_prompt = (
                user_prompt
                + "\n\n[SYSTEM CORRECTION] Your previous response was truncated or not valid JSON. "
                "Please ensure your COMPLETE response fits within the output limit. "
                "Keep feedback concise but substantive (25-80 words per criterion). "
                "Respond with valid JSON only."
            )
            continue

        try:
            return validate_fn(raw_result, *validate_args)
        except ValidationError as exc:
            if attempt == max_attempts - 1:
                raise
            # Append error hint so the LLM can self-correct on retry
            log.warning("Attempt %d validation failed: %s — retrying", attempt + 1, exc)
            current_user_prompt = (
                user_prompt
                + f"\n\n[SYSTEM CORRECTION] Your previous response was invalid: {exc}. "
                "Please fix this issue and respond again with valid JSON."
            )


# ── Main evaluation endpoint ────────────────────────────────────────────────
@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    file: UploadFile = File(...),
    subject: str = Form(...),
    assessment_type: str = Form("IA1"),
):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    if not subject or not subject.strip():
        raise HTTPException(status_code=400, detail="subject is required")

    try:
        # 0. Extract text from the uploaded file
        raw_bytes = await file.read()
        filename = file.filename or "upload.txt"
        assignment_text = extract_text(raw_bytes, filename)

        if not assignment_text or not assignment_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")

        log.info("Extracted %d chars from '%s'", len(assignment_text), filename)

        # Deterministic seed from assignment content (#3)
        seed = generate_seed(assignment_text)
        log.info("Deterministic seed: %d", seed)

        # 1. Fetch QCAA curriculum context (ISMG + mark allocation + conditions)
        log.info("Evaluating: subject=%s, assessment=%s", subject, assessment_type)
        context = build_context(subject, assessment_type)

        assessment = context.get("assessment", {})
        ismg = assessment.get("ismg", [])

        if not ismg:
            raise HTTPException(
                status_code=404,
                detail=f"No ISMG found for subject '{subject}' / assessment '{assessment_type}'. "
                       f"Make sure the scraper has been run for this subject.",
            )

        # 2. RAG — multi-section query for better coverage (#8)
        query_snippet = build_multi_section_query(assignment_text)
        rag_chunks = vector_search(query_snippet, subject=subject)
        log.info("RAG: %d chunks retrieved for %s", len(rag_chunks), subject)

        # 3. Per-criterion evaluation (#12)
        # Each criterion is evaluated independently to prevent cross-criterion bias.
        mark_allocation = assessment.get("mark_allocation", {})
        expected_criteria = mark_allocation.get("criteria", [])
        technique = assessment.get("technique", assessment_type)

        # Build lookup for mark allocation by criterion name
        mark_alloc_map: dict[str, dict] = {}
        for ma in expected_criteria:
            mark_alloc_map[ma.get("criterion", "").strip().lower()] = ma

        criterion_user_prompt = build_criterion_user_prompt(rag_chunks, assignment_text)

        rubric_scores: list[dict] = []
        for criterion_data in ismg:
            crit_name = criterion_data.get("criterion", "Unknown")
            ma_entry = mark_alloc_map.get(crit_name.lower())
            known_max = int(ma_entry["marks"]) if ma_entry else None

            crit_system = build_criterion_system_prompt(
                subject, assessment_type, technique, criterion_data, ma_entry
            )

            # Call with retry — validation auto-retries once on failure (#7)
            crit_result = _call_with_retry(
                crit_system,
                criterion_user_prompt,
                seed=seed,
                validate_fn=validate_single_criterion,
                validate_args=(known_max,),
            )

            rubric_scores.append(crit_result)
            log.info(
                "Criterion '%s': %d/%d band=%s",
                crit_name, crit_result["score"], crit_result["max_score"], crit_result["band"],
            )

        # 4. Generate overall summary via a final call
        overall_score = sum(r["score"] for r in rubric_scores)
        max_overall = sum(r["max_score"] for r in rubric_scores)

        # Build a compact summary prompt for overall feedback
        scores_summary = "\n".join(
            f"- {r['criterion']}: {r['score']}/{r['max_score']} (Band {r['band']})"
            for r in rubric_scores
        )
        overall_system = (
            f"You are an expert QCAA marker for {subject} — {assessment_type}. "
            "Given the per-criterion scores and feedback below, write a concise overall summary "
            "(3-5 sentences) covering the submission's key strengths and areas for improvement. "
            "Do not include generic praise. Be specific and evidence-based. "
            "Respond with ONLY a JSON object: {\"feedback\": \"<summary>\"}"
        )
        overall_user = (
            f"## Per-Criterion Results\n{scores_summary}\n\n"
            f"Overall: {overall_score}/{max_overall}\n\n"
            "Write the overall summary."
        )

        try:
            overall_raw = call_gemini(overall_system, overall_user, seed=seed)
            overall_feedback = overall_raw.get("feedback", "").strip()
        except Exception as exc:
            log.warning("Overall summary generation failed: %s — using fallback", exc)
            overall_feedback = f"Overall score: {overall_score}/{max_overall}."

        result = {
            "rubric_scores": rubric_scores,
            "overall_score": overall_score,
            "max_overall_score": max_overall,
            "feedback": overall_feedback,
            "model_version": GEMINI_MODEL,
            "assignment_text": assignment_text,
        }

        log.info(
            "Grading complete: %d/%d  (%d criteria)",
            result["overall_score"],
            result["max_overall_score"],
            len(result["rubric_scores"]),
        )
        return result

    except ValidationError as exc:
        log.error("Validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))

    except HTTPException:
        raise

    except Exception as exc:
        log.error("Evaluation failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")


# ── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
