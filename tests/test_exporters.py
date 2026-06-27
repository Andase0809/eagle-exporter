from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from eagle_exporter.models import MaterialRecord
from eagle_exporter.services.exporters import (
    ExcelExporter,
    ExportManager,
    JsonExporter,
    MarkdownExporter,
    calc_row_height,
    sanitize_sheet_name,
)


def make_record(tmp_path: Path) -> MaterialRecord:
    image_path = tmp_path / "thumbnail.png"
    Image.new("RGB", (48, 32), color=(120, 90, 160)).save(image_path)
    return MaterialRecord(
        source_dir=tmp_path / "item.info",
        title="客厅灯光灵感",
        desc="柔和的空间光线说明",
        topics=["#家居", "#灯光"],
        image_path=image_path,
        target_folders=["家居素材"],
    )


def test_export_manager_writes_selected_formats(tmp_path: Path) -> None:
    grouped = {"家居素材": [make_record(tmp_path)]}
    manager = ExportManager([ExcelExporter(), MarkdownExporter(), JsonExporter()])

    outputs = manager.export_all(grouped, tmp_path / "eagle_export")

    assert {path.suffix for path in outputs} == {".xlsx", ".md", ".json"}
    for path in outputs:
        assert path.exists()

    markdown = (tmp_path / "eagle_export.md").read_text(encoding="utf-8")
    assert "客厅灯光灵感" in markdown
    assert "#家居 #灯光" in markdown

    payload = json.loads((tmp_path / "eagle_export.json").read_text(encoding="utf-8"))
    assert payload["家居素材"][0]["title"] == "客厅灯光灵感"
    assert payload["家居素材"][0]["topics"] == ["#家居", "#灯光"]


def test_exporters_return_none_for_empty_data(tmp_path: Path) -> None:
    assert ExcelExporter().export({}, tmp_path / "empty.xlsx") is None
    assert MarkdownExporter().export({}, tmp_path / "empty.md") is None
    assert JsonExporter().export({}, tmp_path / "empty.json") is None


def test_sheet_name_and_row_height_helpers() -> None:
    assert sanitize_sheet_name("a/b:c*d?e[f]g") == "a_b_c_d_e_f_g"
    assert len(sanitize_sheet_name("x" * 80)) == 31
    assert calc_row_height("短描述") >= 110
    assert calc_row_height("长描述" * 80) > 110
