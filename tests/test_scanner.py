from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from eagle_exporter.services.scanner import EagleScanner


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def create_material(
    images_dir: Path,
    name: str,
    annotation: str,
    folders: list[str] | None = None,
    ext: str = "jpg",
    dir_name: str | None = None,
) -> Path:
    item_dir = images_dir / f"{dir_name or name}.info"
    item_dir.mkdir(parents=True)
    write_json(
        item_dir / "metadata.json",
        {
            "name": name,
            "annotation": annotation,
            "folders": folders or [],
            "ext": ext,
        },
    )
    Image.new("RGB", (32, 32), color=(80, 120, 180)).save(item_dir / "thumbnail.png")
    return item_dir


def create_library(tmp_path: Path) -> Path:
    library_root = tmp_path / "fixture.library"
    images_dir = library_root / "images"
    images_dir.mkdir(parents=True)
    write_json(
        library_root / "metadata.json",
        {
            "folders": [
                {"id": "folder-a", "name": "内容灵感"},
                {"id": "folder-b", "name": "产品图"},
            ]
        },
    )
    return library_root


def test_scan_groups_materials_by_eagle_folder(tmp_path: Path) -> None:
    library_root = create_library(tmp_path)
    images_dir = library_root / "images"
    create_material(images_dir, "001", "这是一条文案 #灯光[话题]# #家居 @生活薯", ["folder-a"])

    grouped, total = EagleScanner(worker_count=2).scan(library_root)

    assert total == 1
    assert list(grouped) == ["内容灵感"]
    record = grouped["内容灵感"][0]
    assert record.title == "001"
    assert record.desc == "这是一条文案"
    assert record.topics == ["#灯光", "#家居", "@生活薯"]
    assert record.image_path and record.image_path.name == "thumbnail.png"


def test_scan_accepts_images_directory_and_deduplicates_records(tmp_path: Path) -> None:
    library_root = create_library(tmp_path)
    images_dir = library_root / "images"
    annotation = "同一条说明 #收纳"
    create_material(images_dir, "same", annotation, ["folder-a"], dir_name="same-a")
    create_material(images_dir, "same", annotation, ["folder-a"], dir_name="same-b")

    grouped, total = EagleScanner(worker_count=1).scan(images_dir)

    assert total == 2
    assert len(grouped["内容灵感"]) == 1


def test_scan_ignores_video_materials(tmp_path: Path) -> None:
    library_root = create_library(tmp_path)
    create_material(library_root / "images", "video", "视频说明 #素材", ["folder-a"], ext="mp4")

    grouped, total = EagleScanner().scan(library_root)

    assert total == 1
    assert grouped == {}
