"""Validate and normalise the raw JSON returned by the LLM."""

import logging
from typing import Any

from config import GEMINI_MODEL

log = logging.getLogger(__name__)

# Valid QCAA bands
_VALID_BANDS = {"A", "B", "C", "D", "E"}
# Minimum word count for substantive feedback (#6)
_MIN_FEEDBACK_WORDS = 25


class ValidationError(Exception):
    """Raised when the LLM output fails validation."""


def _validate_feedback_quality(feedback: str, criterion: str) -> None:
    """Ensure feedback meets minimum quality bar (#6)."""
    word_count = len(feedback.split())
    if word_count < _MIN_FEEDBACK_WORDS:
        raise ValidationError(
            f"Feedback too short for '{criterion}': {word_count} words "
            f"(minimum {_MIN_FEEDBACK_WORDS}). Feedback must contain substantive analysis."
        )


def _validate_evidence_quotes(quotes: Any, criterion: str) -> list[str]:
    """Validate evidence_quotes array — must be a list of non-empty strings."""
    if not isinstance(quotes, list):
        return []
    cleaned = [q.strip() for q in quotes if isinstance(q, str) and q.strip()]
    # We require at least 1 quote but don't hard-fail — the prompt requests 2-5
    if not cleaned:
        log.warning("No evidence quotes returned for criterion '%s'", criterion)
    return cleaned


def _validate_band_analysis(analysis: Any, criterion: str) -> dict[str, str]:
    """Validate band_analysis dict — should have keys for each QCAA band."""
    if not isinstance(analysis, dict):
        return {}
    cleaned: dict[str, str] = {}
    for band in ("A", "B", "C", "D", "E"):
        val = analysis.get(band, "")
        if isinstance(val, str) and val.strip():
            cleaned[band] = val.strip()
    return cleaned


def validate_and_normalise(
    raw: dict[str, Any],
    expected_criteria: list[dict],
) -> dict[str, Any]:
    """Validate the LLM response against the ISMG mark allocation.

    Parameters
    ----------
    raw : dict
        Parsed JSON from the LLM.
    expected_criteria : list[dict]
        Mark allocation entries, each with keys ``criterion`` and ``marks``.

    Returns
    -------
    dict
        Cleaned and validated response ready to return to the Express backend.

    Raises
    ------
    ValidationError
        If the response is structurally invalid or scores are out of range.
    """
    rubric_scores = raw.get("rubric_scores")
    if not isinstance(rubric_scores, list) or len(rubric_scores) == 0:
        raise ValidationError("Missing or empty rubric_scores array")

    # Build a lookup of max marks per criterion
    max_marks_map: dict[str, int] = {}
    for entry in expected_criteria:
        name = entry.get("criterion", "").strip()
        marks = entry.get("marks", 0)
        if name:
            max_marks_map[name.lower()] = int(marks)

    cleaned_scores: list[dict[str, Any]] = []
    running_total = 0
    running_max = 0

    for item in rubric_scores:
        criterion = item.get("criterion", "").strip()
        score = item.get("score")
        max_score = item.get("max_score")
        band = item.get("band", "").strip().upper()
        feedback = item.get("feedback", "").strip()
        improvement = item.get("improvement", "").strip()

        if not criterion:
            raise ValidationError(f"rubric_scores entry missing criterion name: {item}")

        # Coerce to int
        try:
            score = int(score)
            max_score = int(max_score)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Non-integer score/max_score for criterion '{criterion}': "
                f"score={item.get('score')}, max_score={item.get('max_score')}"
            )

        # Check against known max marks if we have them
        known_max = max_marks_map.get(criterion.lower())
        if known_max is not None:
            max_score = known_max  # authoritative source
        if score < 0 or score > max_score:
            raise ValidationError(
                f"Score {score} out of range [0, {max_score}] for '{criterion}'"
            )

        # Band must be a valid QCAA band (#6)
        if band not in _VALID_BANDS:
            raise ValidationError(
                f"Invalid band '{band}' for '{criterion}'. Must be one of: {', '.join(sorted(_VALID_BANDS))}"
            )

        # Feedback quality gate (#6)
        _validate_feedback_quality(feedback, criterion)

        running_total += score
        running_max += max_score

        cleaned_scores.append(
            {
                "criterion": criterion,
                "score": score,
                "max_score": max_score,
                "band": band,
                "feedback": feedback,
                "improvement": improvement,
                "evidence_quotes": _validate_evidence_quotes(item.get("evidence_quotes", []), criterion),
                "band_analysis": _validate_band_analysis(item.get("band_analysis", {}), criterion),
            }
        )

    overall_feedback = raw.get("feedback", "").strip()

    return {
        "rubric_scores": cleaned_scores,
        "overall_score": running_total,
        "max_overall_score": running_max,
        "feedback": overall_feedback,
        "model_version": GEMINI_MODEL,
    }


def validate_single_criterion(raw: dict[str, Any], max_score: int | None = None) -> dict[str, Any]:
    """Validate a single criterion result from per-criterion evaluation (#12).

    Parameters
    ----------
    raw : dict
        Parsed JSON for one criterion from the LLM.
    max_score : int or None
        Authoritative max score from mark allocation if known.

    Returns
    -------
    dict
        Cleaned single-criterion result.

    Raises
    ------
    ValidationError
        If the result is invalid.
    """
    criterion = raw.get("criterion", "").strip()
    if not criterion:
        raise ValidationError("Missing criterion name in single-criterion response")

    try:
        score = int(raw.get("score", 0))
        raw_max = int(raw.get("max_score", 0))
    except (TypeError, ValueError):
        raise ValidationError(
            f"Non-integer score/max_score for criterion '{criterion}'"
        )

    effective_max = max_score if max_score is not None else raw_max

    if score < 0 or score > effective_max:
        raise ValidationError(
            f"Score {score} out of range [0, {effective_max}] for '{criterion}'"
        )

    band = raw.get("band", "").strip().upper()
    if band not in _VALID_BANDS:
        raise ValidationError(
            f"Invalid band '{band}' for '{criterion}'. Must be one of: {', '.join(sorted(_VALID_BANDS))}"
        )

    feedback = raw.get("feedback", "").strip()
    _validate_feedback_quality(feedback, criterion)

    return {
        "criterion": criterion,
        "score": score,
        "max_score": effective_max,
        "band": band,
        "feedback": feedback,
        "improvement": raw.get("improvement", "").strip(),
        "evidence_quotes": _validate_evidence_quotes(raw.get("evidence_quotes", []), criterion),
        "band_analysis": _validate_band_analysis(raw.get("band_analysis", {}), criterion),
    }
