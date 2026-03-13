"""Fetch structured curriculum context from Supabase for a given subject + assessment."""

import logging
from typing import Any
from urllib.parse import quote

import requests

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

log = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_assessment_context(subject: str, assessment_type: str) -> dict[str, Any]:
    """Fetch the assessment row from qcaa_curriculum.

    Returns the 'content' JSONB which contains:
    - assessment, subject, technique
    - criteria, conditions
    - ismg (list of {criterion, bands})
    - mark_allocation {criteria: [{criterion, objectives, marks}], total_marks}
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/qcaa_curriculum"
        f"?subject=eq.{quote(subject)}"
        f"&section_type=eq.assessment"
        f"&section_key=eq.{quote(assessment_type)}"
        f"&select=content"
        f"&limit=1"
    )
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200 or not resp.json():
        log.warning("No curriculum assessment found for %s / %s", subject, assessment_type)
        return {}
    return resp.json()[0].get("content", {})


def fetch_unit_contexts(subject: str) -> list[dict[str, Any]]:
    """Fetch all unit rows for a subject from qcaa_curriculum.

    Returns a list of content dicts, each with:
    - unit, subject, title, description, topics
    """
    url = (
        f"{SUPABASE_URL}/rest/v1/qcaa_curriculum"
        f"?subject=eq.{quote(subject)}"
        f"&section_type=eq.unit"
        f"&select=content"
        f"&order=section_key"
    )
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        log.warning("Failed to fetch units for %s: %d", subject, resp.status_code)
        return []
    return [row["content"] for row in resp.json()]


def build_context(subject: str, assessment_type: str) -> dict[str, Any]:
    """Build the full curriculum context dict used by the prompt builder.

    Returns {
        "assessment": {...},     # full assessment content with ISMG + mark allocs
        "units": [...],          # all unit contents for this subject
        "subject": str,
        "assessment_type": str,
    }
    """
    assessment = fetch_assessment_context(subject, assessment_type)
    units = fetch_unit_contexts(subject)

    log.info(
        "Context: %s / %s — assessment=%s, ismg=%d criteria, units=%d",
        subject,
        assessment_type,
        "found" if assessment else "MISSING",
        len(assessment.get("ismg", [])),
        len(units),
    )

    return {
        "subject": subject,
        "assessment_type": assessment_type,
        "assessment": assessment,
        "units": units,
    }
