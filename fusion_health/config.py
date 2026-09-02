from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _parse_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off", ""):
        return False
    logger.warning("Unrecognized bool value %r, treating as False", v)
    return False


@dataclass
class HealthConfig:
    mlx_url: str = "http://localhost:11432/v1"
    model: str = "Qwen3.5-9B-4bit"
    mlx_api_key: str = ""
    mlx_route: str = ""
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: float = 60.0
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    rules_dir: Path = field(default_factory=lambda: Path(__file__).parent / "compliance" / "rules")
    templates_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "templates")
    artifacts_url: str = "http://localhost:11451"
    api_port: int = 11469
    literature_cache_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "lit_cache")
    pubmed_enabled: bool = True
    semantic_scholar_enabled: bool = True
    offline: bool = False
    rate_limit_rpm: int = 0
    audit_log_path: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "audit.log")
    session_ttl_seconds: int = 1800
    max_context_chars: int = 96000

    @classmethod
    def from_env(cls) -> HealthConfig:
        cfg = cls()
        env_map = {
            "FUSION_HEALTH_MLX_URL": ("mlx_url", str),
            "FUSION_HEALTH_MODEL": ("model", str),
            "FUSION_MLX_API_KEY": ("mlx_api_key", str),
            "FUSION_HEALTH_MLX_API_KEY": ("mlx_api_key", str),
            "FUSION_HEALTH_MLX_ROUTE": ("mlx_route", str),
            "FUSION_HEALTH_TEMPERATURE": ("temperature", float),
            "FUSION_HEALTH_MAX_TOKENS": ("max_tokens", int),
            "FUSION_HEALTH_TIMEOUT": ("timeout", float),
            "FUSION_ARTIFACTS_URL": ("artifacts_url", str),
            "FUSION_HEALTH_API_PORT": ("api_port", int),
            "FUSION_HEALTH_RATE_LIMIT_RPM": ("rate_limit_rpm", int),
            "FUSION_HEALTH_SESSION_TTL": ("session_ttl_seconds", int),
        }
        for env_key, (attr, cast) in env_map.items():
            val = os.getenv(env_key)
            if val is not None:
                setattr(cfg, attr, cast(val))

        if os.getenv("FUSION_HEALTH_PUBMED_ENABLED", "1") == "0":
            cfg.pubmed_enabled = False
        if os.getenv("FUSION_HEALTH_OFFLINE", "0") == "1":
            cfg.offline = True

        yaml_path = Path.home() / ".fusion-health" / "config.yaml"
        if yaml_path.exists():
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    overrides = yaml.safe_load(f) or {}
                for k, v in overrides.items():
                    if not hasattr(cfg, k):
                        continue
                    if isinstance(getattr(cfg, k), bool):
                        setattr(cfg, k, _parse_bool(v))
                    else:
                        setattr(cfg, k, type(getattr(cfg, k))(v))
                logger.info("Loaded config overrides from %s", yaml_path)
            except Exception as e:
                logger.warning("Failed to load config.yaml: %s", e)

        if not cfg.mlx_api_key:
            settings_path = Path.home() / ".fusion-mlx" / "settings.json"
            try:
                if settings_path.exists():
                    import json
                    with open(settings_path, encoding="utf-8") as f:
                        s = json.load(f) or {}
                    key = s.get("auth", {}).get("api_key", "") if isinstance(s, dict) else ""
                    if key:
                        cfg.mlx_api_key = key
                        logger.info("Loaded mlx_api_key from %s", settings_path)
            except Exception as e:
                logger.warning("Failed to read fusion-mlx settings.json: %s", e)

        logger.info(
            "HealthConfig: model=%s, mlx_url=%s, offline=%s",
            cfg.model, cfg.mlx_url, cfg.offline,
        )
        return cfg
