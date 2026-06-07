"""Local config store for SpiderPilot settings (API key, model, etc)."""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".spiderpilot_config.json"

DEFAULTS = {
    "api_key": "",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-v4-flash",
}

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {**DEFAULTS}
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {**DEFAULTS, **data}

def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get(key: str) -> str:
    return str(load_config().get(key, ""))

def set_(key: str, value: str) -> None:
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
