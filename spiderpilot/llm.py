"""Minimal LLM client for SpiderPilot.

Uses OpenAI-compatible API. Reads OPENAI_API_KEY and OPENAI_BASE_URL from env.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests


def get_client() -> dict[str, str]:
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
    base = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return {"key": key, "base": base.rstrip("/")}


def chat(
    messages: list[dict[str, str]],
    model: str = "deepseek-v4-flash",
    temperature: float = 0.1,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> str:
    cfg = get_client()
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    resp = requests.post(
        f"{cfg['base']}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def chat_json(
    messages: list[dict[str, str]],
    model: str = "deepseek-v4-flash",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    raw = chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        stripped = [line for line in lines if not line.strip().startswith("```")]
        raw = "\n".join(stripped)
    return json.loads(raw)
