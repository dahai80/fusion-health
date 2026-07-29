from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class HealthConfig:
    mlx_url: str = "http://localhost:11434/v1"
    model: str = "qwen3.5-9b"
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: float = 60.0
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    rules_dir: Path = field(default_factory=lambda: Path(__file__).parent / "compliance" / "rules")
    templates_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "templates")
    artifacts_url: str = "http://localhost:8892"
    literature_cache_dir: Path = field(default_factory=lambda: Path.home() / ".fusion-health" / "lit_cache")
    pubmed_enabled: bool = True
    semantic_scholar_enabled: bool = True
    offline: bool = False

    @classmethod
    def from_env(cls) -> HealthConfig:
        cfg = cls()
        env_map = {
            "FUSION_HEALTH_MLX_URL": ("mlx_url", str),
            "FUSION_HEALTH_MODEL": ("model", str),
            "FUSION_HEALTH_TEMPERATURE": ("temperature", float),
            "FUSION_HEALTH_MAX_TOKENS": ("max_tokens", int),
            "FUSION_HEALTH_TIMEOUT": ("timeout", float),
            "FUSION_ARTIFACTS_URL": ("artifacts_url", str),
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
                    if hasattr(cfg, k):
                        setattr(cfg, k, type(getattr(cfg, k))(v))
                logger.info("Loaded config overrides from %s", yaml_path)
            except Exception as e:
                logger.warning("Failed to load config.yaml: %s", e)

        logger.info(
            "HealthConfig: model=%s, mlx_url=%s, offline=%s",
            cfg.model, cfg.mlx_url, cfg.offline,
        )
        return cfg
