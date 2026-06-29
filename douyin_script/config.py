"""Configuration loader — merges config.example defaults with config.local.yaml and env."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(os.getenv("WINT_DY_EXAMPLE_CONFIG", str(ROOT / "config.example.yaml")))
LOCAL_CONFIG = Path(os.getenv("WINT_DY_CONFIG", str(ROOT / "config.local.yaml")))


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(root: Path | None = None) -> dict[str, Any]:
    _ = root  # legacy; use WINT_DY_CONFIG env for sandbox overrides
    cfg = _load_yaml(DEFAULT_CONFIG)
    if LOCAL_CONFIG.exists():
        cfg = _deep_merge(cfg, _load_yaml(LOCAL_CONFIG))

    secrets = cfg.setdefault("secrets", {})
    env_map = {
        "dashscope_api_key": "DASHSCOPE_API_KEY",
        "llm_api_key": "LLM_API_KEY",
        "douyin_cookie": "DOUYIN_COOKIE",
    }
    for key, env_name in env_map.items():
        if os.getenv(env_name):
            secrets[key] = os.getenv(env_name)
        elif secrets.get(key):
            os.environ.setdefault(env_name, secrets[key])

    if secrets.get("dashscope_api_key"):
        os.environ.setdefault("DASHSCOPE_API_KEY", secrets["dashscope_api_key"])

    llm = cfg.setdefault("llm", {})
    if os.getenv("DY_LLM_ENABLED", "").lower() in {"1", "true", "yes"}:
        llm["enabled"] = True

    return cfg


def project_root(cfg: dict) -> Path:
    rel = cfg.get("project_root", ".")
    return (ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)


def library_dir(cfg: dict) -> Path:
    return project_root(cfg) / cfg["paths"]["library"]


def logs_dir(cfg: dict) -> Path:
    return project_root(cfg) / cfg["paths"]["logs"]


def manifest_path(cfg: dict) -> Path:
    return project_root(cfg) / cfg["paths"]["manifest"]
