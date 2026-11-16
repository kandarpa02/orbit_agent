from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORBIT_",
        case_sensitive=False,
        extra="ignore",
    )

    model: str = Field(default="gpt-4o-mini")
    base_url: str = Field(default="https://api.openai.com/v1")
    api_key: str = Field(default="demo-key")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    app_name: str = Field(default="ORBIT")

    @classmethod
    def from_file(cls, config_path: str | Path | None = None) -> "AgentSettings":
        config: dict[str, Any] = {}

        if config_path is not None:
            candidate = Path(config_path).expanduser().resolve()
            if candidate.exists():
                raw = candidate.read_text(encoding="utf-8")
                if candidate.suffix.lower() == ".json":
                    config = json.loads(raw)
                else:
                    for line in raw.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip().strip('"\'')

        values = dict(os.environ)
        values = {k.lower().replace("orbit_", "", 1): v for k, v in values.items() if k.lower().startswith("orbit_")}
        config = {**config, **values}

        return cls(**config)


def load_settings(config_path: str | Path | None = None) -> AgentSettings:
    return AgentSettings.from_file(config_path)


class ServeConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "demo-key"
    model: str = "gpt-4o-mini"

    @classmethod
    def from_file(cls, config_path: str | Path | None = None) -> "ServeConfig":
        settings = AgentSettings.from_file(config_path)
        return cls(
            host=settings.host,
            port=settings.port,
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
        )
