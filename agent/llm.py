"""Vultr Serverless Inference client (OpenAI-compatible).

ALL LLM calls in NightShift Ops go through Vultr Serverless Inference —
a hard requirement of Challenge 01. Primary model with a configured fallback.
"""

from __future__ import annotations

import json
import re

import httpx

from .config import settings


class LLMError(Exception):
    pass


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 900) -> str:
    if not settings.inference_api_key:
        raise LLMError("VULTR_INFERENCE_API_KEY is not configured")
    last_err: Exception | None = None
    for model in (settings.inference_model, settings.inference_fallback_model):
        try:
            resp = httpx.post(
                f"{settings.inference_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.inference_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=90.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # try the fallback model once
            last_err = exc
    raise LLMError(f"Inference call failed on both models: {last_err}")


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (handles code fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("No JSON object found in model reply")
        candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model reply was not valid JSON: {exc}") from exc
