"""FastAPI AI grading service — evaluates student work against QCAA rubrics."""

import logging
import sys
import traceback

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from config import PORT, GEMINI_API_KEY
from text_extractor import extract_text
from context_builder import build_context
from vector_search import search as vector_search
from prompt_builder import build_messages
from llm_client import call_gemini
from response_parser import validate_and_normalise, ValidationError

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

app = FastAPI(title="QCAA AI Grading Service", version="1.0.0")


# ── Response models ─────────────────────────────────────────────────────────
class CriterionResult(BaseModel):
    criterion: str
    score: int
    max_score: int
    band: str = ""
    feedback: str = ""
    improvement: str = ""


class EvaluateResponse(BaseModel):
    rubric_scores: list[CriterionResult]
    overall_score: int
    max_overall_score: int
    feedback: str
    model_version: str


# ── Health check ────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model": "gemini-2.5-flash"}


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

        # 2. RAG — retrieve relevant syllabus chunks
        query_snippet = assignment_text[:500]
        rag_chunks = vector_search(query_snippet, subject=subject)
        log.info("RAG: %d chunks retrieved for %s", len(rag_chunks), subject)

        # 3. Build prompts
        system_prompt, user_prompt = build_messages(context, rag_chunks, assignment_text)

        # 4. Call Gemini
        raw_result = call_gemini(system_prompt, user_prompt)

        # 5. Validate and normalise
        mark_allocation = assessment.get("mark_allocation", {})
        expected_criteria = mark_allocation.get("criteria", [])

        result = validate_and_normalise(raw_result, expected_criteria)

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
