from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(slots=True)
class MaterialRecord:
    """A normalized record extracted from one Eagle material folder."""

    source_dir: Path
    title: str
    desc: str
    topics: List[str]
    image_path: Optional[Path]
    target_folders: List[str]
    metadata: Dict = field(default_factory=dict)

    @property
    def topics_text(self) -> str:
        return " ".join(self.topics)

    @property
    def dedup_key(self) -> str:
        return f"{self.title}|{self.desc}"


@dataclass(slots=True)
class AppConfig:
    library_path: str = ""
    save_path: str = ""
    theme: str = "Light"
    enable_toast: bool = True
    worker_count: int = 8
    export_excel: bool = True
    export_markdown: bool = True
    export_json: bool = False


@dataclass(slots=True)
class ExportSelection:
    include_excel: bool = True
    include_markdown: bool = True
    include_json: bool = False
