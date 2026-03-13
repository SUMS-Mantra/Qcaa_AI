"""Validate and normalise the raw JSON returned by the LLM."""

import logging
from typing import Any

from config import GEMINI_MODEL

log = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when the LLM output fails validation."""


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

        if band and band not in {"A", "B", "C", "D", "E"}:
            band = ""  # drop invalid band rather than fail

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
