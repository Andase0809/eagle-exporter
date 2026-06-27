from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ..models import MaterialRecord

VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm", "wmv", "m4v"}
SPECIAL_AT_TAGS = [
    "@生活薯",
    "@摄影薯",
    "@走走薯",
    "@薯队长",
    "@小红书设计周",
    "@发发薯",
    "@小红书创作学院",
    "@热点薯",
    "@日常薯",
]

ProgressCallback = Optional[Callable[[int, int], None]]


class EagleScanner:
    def __init__(self, worker_count: int = 8) -> None:
        self.worker_count = max(1, worker_count)
        self._dedup_set: set[str] = set()
        self._dedup_lock = Lock()

    def scan(
        self,
        root_dir: str | Path,
        progress_callback: ProgressCallback = None,
    ) -> Tuple[Dict[str, List[MaterialRecord]], int]:
        library_root, images_dir = self._resolve_library_paths(Path(root_dir))
        folder_map = self._build_folder_map(library_root)

        try:
            material_dirs = [
                item.path
                for item in os.scandir(images_dir)
                if item.is_dir() and item.name.endswith(".info")
            ]
        except Exception:
            return {}, 0

        total = len(material_dirs)
        if total == 0:
            return {}, 0

        records: List[MaterialRecord] = []
        processed = 0

        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            futures = {
                executor.submit(self._process_material, Path(path), folder_map): path
                for path in material_dirs
            }
            for future in as_completed(futures):
                processed += 1
                if progress_callback:
                    progress_callback(processed, total)
                record = future.result()
                if record:
                    records.append(record)

        grouped = self._group_by_folder(records)
        return grouped, total

    def _resolve_library_paths(self, root_dir: Path) -> Tuple[Path, Path]:
        if root_dir.name.endswith(".library") or (root_dir / "metadata.json").exists():
            return root_dir, root_dir / "images"
        if root_dir.name.lower() == "images":
            return root_dir.parent, root_dir
        return root_dir, root_dir

    def _build_folder_map(self, library_root: Path) -> Dict[str, str]:
        metadata_path = library_root / "metadata.json"
        if not metadata_path.exists():
            return {}

        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}

        folder_map: Dict[str, str] = {}

        def walk(items: Iterable[dict]) -> None:
            for item in items:
                folder_id = item.get("id")
                folder_name = item.get("name")
                if folder_id and folder_name:
                    folder_map[folder_id] = folder_name
                children = item.get("children")
                if isinstance(children, list):
                    walk(children)

        walk(data.get("folders", []))
        return folder_map

    def _process_material(
        self,
        material_dir: Path,
        folder_map: Dict[str, str],
    ) -> Optional[MaterialRecord]:
        metadata_file = material_dir / "metadata.json"
        if not metadata_file.exists():
            return None

        try:
            filenames = os.listdir(material_dir)
        except PermissionError:
            return None

        thumbnail_file = next(
            (
                material_dir / name
                for name in filenames
                if "thumbnail" in name.lower() and name.lower().endswith(".png")
            ),
            None,
        )
        if thumbnail_file is None:
            return None

        try:
            raw = json.loads(metadata_file.read_text(encoding="utf-8-sig"))
        except Exception:
            return None

        if str(raw.get("ext", "")).lower() in VIDEO_EXTS:
            return None

        title = re.sub(r"\s+", " ", str(raw.get("name", "") or "未命名")).strip()
        annotation = str(raw.get("annotation", "") or "")
        target_folders = [folder_map[fid] for fid in raw.get("folders", []) if fid in folder_map]
        if not target_folders:
            target_folders = ["未分类素材"]

        desc, topics = self._extract_desc_and_topics(annotation)
        if not desc and not topics:
            return None

        record = MaterialRecord(
            source_dir=material_dir,
            title=title,
            desc=desc,
            topics=topics,
            image_path=thumbnail_file,
            target_folders=target_folders,
            metadata=raw,
        )

        with self._dedup_lock:
            if record.dedup_key in self._dedup_set:
                return None
            self._dedup_set.add(record.dedup_key)

        return record

    def _extract_desc_and_topics(self, annotation: str) -> Tuple[str, List[str]]:
        topics: List[str] = []

        def extract_xhs_tag(match: re.Match[str]) -> str:
            topics.append(match.group(0).replace("[话题]#", "").strip())
            return ""

        desc = re.sub(r"#[^\s#]+?\[话题\]#", extract_xhs_tag, annotation)

        def extract_hash_tag(match: re.Match[str]) -> str:
            topics.append(match.group(0).strip())
            return ""

        desc = re.sub(r"#[^\s,。，！!？?、；;.,:：()（）\[\]【】]+", extract_hash_tag, desc)

        for at_tag in SPECIAL_AT_TAGS:
            if at_tag in desc:
                topics.append(at_tag)
                desc = desc.replace(at_tag, "")

        unique_topics = list(dict.fromkeys(topics))
        desc = re.sub(r"[ \t]+", " ", desc).strip()
        desc = re.sub(r"\n\s*\n", "\n", desc).strip()
        return desc, unique_topics

    def _group_by_folder(self, records: List[MaterialRecord]) -> Dict[str, List[MaterialRecord]]:
        grouped: Dict[str, List[MaterialRecord]] = {}
        for record in records:
            for folder in record.target_folders:
                grouped.setdefault(folder, []).append(record)
        return grouped
