from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import AppConfig

CONFIG_FILE = Path(__file__).resolve().parent / "eagle_config.json"


class ConfigManager:
    def __init__(self, path: Path = CONFIG_FILE) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return AppConfig(**data)
            except Exception:
                pass
        return AppConfig()

    def save(self, config: AppConfig) -> None:
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
