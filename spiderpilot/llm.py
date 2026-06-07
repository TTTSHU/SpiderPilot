"""Minimal LLM client for SpiderPilot."""

import json
import os
from typing import Any

import requests
from spiderpilot.config_store import load_config


def get_client() -> dict[str, str]:
    cfg = load_config()
    key = cfg.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY") or ""
    base = cfg.get("api_base") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    if not key:
        raise RuntimeError("API key not set. Please configure it via Settings in the Web UI or set OPENAI_API_KEY env var.")
    return {"key": key, "base": base.rstrip("/")}


def get_model() -> str:
    cfg = load_config()
    return cfg.get("model", "deepseek-v4-flash")


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> str:
    cfg = get_client()
    body: dict[str, Any] = {
        "model": model or get_model(),
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
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    raw = chat(messages, model=model, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join([line for line in lines if not line.strip().startswith("```")])
    return json.loads(raw)
