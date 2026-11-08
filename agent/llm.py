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


def chat(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 900,
    model: str | None = None,
) -> str:
    if not settings.inference_api_key:
        raise LLMError("VULTR_INFERENCE_API_KEY is not configured")
    models = (model,) if model else (settings.inference_model, settings.inference_fallback_model)
    last_err: Exception | None = None
    for m in models:
        try:
            resp = httpx.post(
                f"{settings.inference_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.inference_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": m,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # try the next model
            last_err = exc
    raise LLMError(f"Inference call failed on all tried models: {last_err}")


def chat_json(messages: list[dict], temperature: float = 0.2, max_tokens: int = 900) -> dict:
    """Chat that must yield a JSON object. A model can answer a successful
    HTTP call with unparseable prose — that is a failed attempt too, so the
    rotation covers parse failures, not just transport failures:
    primary -> fallback -> primary, then give up."""
    order = (
        settings.inference_model,
        settings.inference_fallback_model,
        settings.inference_model,
    )
    last_err: Exception | None = None
    for m in order:
        try:
            return extract_json(chat(messages, temperature, max_tokens, model=m))
        except Exception as exc:
            last_err = exc
    raise LLMError(f"No parseable JSON from any model attempt: {last_err}")


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
