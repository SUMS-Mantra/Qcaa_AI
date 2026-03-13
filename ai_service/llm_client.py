"""Gemini LLM client via google-genai SDK — deterministic config."""

import json
import logging

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_TOP_P,
    GEMINI_TOP_K,
    GEMINI_MAX_TOKENS,
)

log = logging.getLogger(__name__)

# Initialise the client once at module level
_client = genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(system_prompt: str, user_prompt: str, seed: int = 0) -> dict:
    """Send prompts to Gemini and return the parsed JSON response.

    Parameters
    ----------
    system_prompt : str
        System-level instructions.
    user_prompt : str
        User-level prompt content.
    seed : int
        Deterministic seed derived from submission content (#3).
        Identical inputs produce identical outputs.

    Raises
    ------
    ValueError
        If the response is not valid JSON.
    """
    log.info(
        "Calling Gemini model=%s temp=%.1f top_p=%.1f top_k=%d seed=%d",
        GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_TOP_P, GEMINI_TOP_K, seed,
    )

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=GEMINI_TEMPERATURE,
            top_p=GEMINI_TOP_P,
            top_k=GEMINI_TOP_K,
            seed=seed,
            max_output_tokens=GEMINI_MAX_TOKENS,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text
    if not raw_text:
        raise ValueError("Gemini returned an empty response")

    log.debug("Raw Gemini response: %s", raw_text[:500])

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini response is not valid JSON: {exc}\n{raw_text[:1000]}")
