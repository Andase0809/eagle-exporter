from __future__ import annotations

import io
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import xlsxwriter
from PIL import Image

from ..models import MaterialRecord


class BaseExporter(ABC):
    extension: str = ""

    @abstractmethod
    def export(self, grouped_data: Dict[str, List[MaterialRecord]], output_path: Path) -> Optional[Path]:
        raise NotImplementedError


class ExcelExporter(BaseExporter):
    extension = ".xlsx"

    def export(self, grouped_data: Dict[str, List[MaterialRecord]], output_path: Path) -> Optional[Path]:
        if not grouped_data:
            return None

        with xlsxwriter.Workbook(str(output_path)) as workbook:
            hdr_fmt = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 11,
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": "#2B2D30",
                    "align": "center",
                    "valign": "vcenter",
                    "border": 1,
                }
            )
            txt_fmt = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "valign": "vcenter",
                    "text_wrap": True,
                    "border": 1,
                }
            )
            ctr_fmt = workbook.add_format(
                {
                    "font_name": "微软雅黑",
                    "font_size": 10,
                    "align": "center",
                    "valign": "vcenter",
                    "border": 1,
                    "text_wrap": True,
                }
            )
            img_cell_fmt = workbook.add_format({"border": 1, "align": "center", "valign": "vcenter"})

            col_w_px = 154
            index = 0
            for folder_name, records in grouped_data.items():
                if not records:
                    continue
                index += 1
                sheet_name = sanitize_sheet_name(folder_name) or f"分类_{index}"
                try:
                    worksheet = workbook.add_worksheet(sheet_name)
                except Exception:
                    worksheet = workbook.add_worksheet(f"分类_{index}")

                worksheet.set_column("A:A", 8)
                worksheet.set_column("B:B", 28)
                worksheet.set_column("C:C", 22)
                worksheet.set_column("D:D", 55)
                worksheet.set_column("E:E", 25)
                worksheet.set_row(0, 32)

                for col, header in enumerate(["【编号】", "【标题】", "【图片】", "【内容描述】", "【话题】"]):
                    worksheet.write(0, col, header, hdr_fmt)

                for row, item in enumerate(records, start=1):
                    row_height_pts = calc_row_height(item.desc)
                    worksheet.set_row(row, row_height_pts)

                    worksheet.write(row, 0, row, ctr_fmt)
                    worksheet.write(row, 1, item.title, txt_fmt)
                    worksheet.write(row, 2, "", img_cell_fmt)
                    worksheet.write(row, 3, item.desc, txt_fmt)
                    worksheet.write(row, 4, item.topics_text, ctr_fmt)

                    if item.image_path and item.image_path.exists():
                        self._insert_image(worksheet, row, col_w_px, row_height_pts, item.image_path, index)

        return output_path

    def _insert_image(self, worksheet, row: int, col_w_px: int, row_height_pts: float, image_path: Path, index: int) -> None:
        try:
            with Image.open(image_path) as img:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA")
                w, h = img.size
                row_h_px = int(row_height_pts * 1.3333)
                padding = 10
                max_w = col_w_px - padding
                max_h = row_h_px - padding
                scale = min(max_w / w, max_h / h)
                if scale > 1:
                    scale = 1
                actual_w = w * scale
                actual_h = h * scale
                x_offset = int((col_w_px - actual_w) / 2)
                y_offset = int((row_h_px - actual_h) / 2)

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                worksheet.insert_image(
                    row,
                    2,
                    f"img_{index}_{row}.png",
                    {
                        "image_data": buf,
                        "x_scale": scale,
                        "y_scale": scale,
                        "object_position": 1,
                        "x_offset": x_offset,
                        "y_offset": y_offset,
                    },
                )
        except Exception:
            worksheet.write(row, 2, "图片加载失败")


class MarkdownExporter(BaseExporter):
    extension = ".md"

    def export(self, grouped_data: Dict[str, List[MaterialRecord]], output_path: Path) -> Optional[Path]:
        if not grouped_data:
            return None

        with output_path.open("w", encoding="utf-8") as f:
            for folder_name, records in grouped_data.items():
                if not records:
                    continue
                f.write(
                    f"# 📁 {folder_name}\n\n> 🕒 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
                )
                for index, item in enumerate(records, start=1):
                    desc = re.sub(r"(?m)^#+\s", "🏷️ ", item.desc)
                    f.write(f"### 📝 文案编号：[{index:02d}] {item.title or '未命名'}\n\n")
                    if desc:
                        f.write(f"**【内容描述】**：\n{desc}\n\n")
                    if item.topics_text:
                        f.write(f"**【话题】**：\n{item.topics_text}\n\n")
                    f.write("---\n\n")
        return output_path


class JsonExporter(BaseExporter):
    extension = ".json"

    def export(self, grouped_data: Dict[str, List[MaterialRecord]], output_path: Path) -> Optional[Path]:
        if not grouped_data:
            return None

        payload = {
            folder_name: [
                {
                    "title": item.title,
                    "desc": item.desc,
                    "topics": item.topics,
                    "image_path": str(item.image_path) if item.image_path else None,
                    "source_dir": str(item.source_dir),
                }
                for item in records
            ]
            for folder_name, records in grouped_data.items()
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path


class ExportManager:
    def __init__(self, exporters: Iterable[BaseExporter]) -> None:
        self.exporters = list(exporters)

    def export_all(self, grouped_data: Dict[str, List[MaterialRecord]], base_output_path: Path) -> List[Path]:
        outputs: List[Path] = []
        for exporter in self.exporters:
            out = exporter.export(grouped_data, base_output_path.with_suffix(exporter.extension))
            if out is not None:
                outputs.append(out)
        return outputs


def calc_row_height(desc: str) -> int:
    lines = desc.count("\n") + max(1, len(desc) // 40)
    return max(110, lines * 16 + 20)


def sanitize_sheet_name(name: str) -> str:
    return re.sub(r"[\\/?*:\[\]]", "_", name)[:31]
