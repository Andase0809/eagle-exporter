from __future__ import annotations

import os
import subprocess
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

from ..config import ConfigManager
from ..models import AppConfig, ExportSelection, MaterialRecord
from ..services.exporters import ExcelExporter, ExportManager, JsonExporter, MarkdownExporter
from ..services.scanner import EagleScanner
from ..utils.logging_utils import attach_ui_handler, build_logger


class ToastNotification(ctk.CTkToplevel):
    def __init__(self, master, title: str, message: str, target_folder: str) -> None:
        super().__init__(master)
        self.target_folder = target_folder
        self.countdown = 4
        self.after_id = None
        self.alpha = 0.0

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2B2D30" if is_dark else "#F3F4F6"
        border_color = "#45474A" if is_dark else "#D1D5DB"
        text_color = "#D1D5DB" if is_dark else "#374151"

        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=bg_color, border_width=1, border_color=border_color)
        frame.pack(fill="both", expand=True)

        ctk.CTkButton(
            frame,
            text="✕",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#EF4444",
            text_color="#9CA3AF",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.fade_out,
        ).place(relx=1.0, rely=0.0, x=-5, y=5, anchor="ne")

        ctk.CTkLabel(
            frame,
            text=f"✅ {title}",
            font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),
            text_color="#10B981",
        ).pack(anchor="w", padx=18, pady=(15, 5))

        ctk.CTkLabel(
            frame,
            text=message,
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color=text_color,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 15))

        bottom_box = ctk.CTkFrame(frame, fg_color="transparent")
        bottom_box.pack(fill="x", padx=18, pady=(0, 18))

        ctk.CTkButton(
            bottom_box,
            text="立即打开所在目录",
            height=30,
            width=120,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12, weight="bold"),
            command=self.on_click,
        ).pack(side="left")

        self.timer_lbl = ctk.CTkLabel(
            bottom_box,
            text=f"{self.countdown}s 后自动关闭",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color="#9CA3AF",
        )
        self.timer_lbl.pack(side="right", padx=(10, 0))

        self.update_idletasks()
        width, height = 320, self.winfo_reqheight() + 5
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = int(sw - width - 20)
        y = int(sh - height - 70)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.fade_in()
        self.tick()

    def tick(self) -> None:
        self.countdown -= 1
        if self.countdown > 0:
            self.timer_lbl.configure(text=f"{self.countdown}s 后自动关闭")
            self.after_id = self.after(1000, self.tick)
        else:
            self.fade_out()

    def fade_in(self) -> None:
        if self.alpha < 0.95:
            self.alpha += 0.05
            self.attributes("-alpha", self.alpha)
            self.after(20, self.fade_in)

    def fade_out(self) -> None:
        if self.alpha > 0:
            self.alpha -= 0.05
            self.attributes("-alpha", self.alpha)
            self.after(15, self.fade_out)
        else:
            if self.after_id:
                try:
                    self.after_cancel(self.after_id)
                except Exception:
                    pass
            self.destroy()

    def on_click(self) -> None:
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        try:
            if os.name == "nt":
                os.startfile(self.target_folder)
            elif os.name == "posix":
                subprocess.Popen(["xdg-open", self.target_folder])
        except Exception:
            pass
        self.fade_out()


class EagleExporterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config_manager = ConfigManager()
        self.app_config: AppConfig = self.config_manager.load()
        self.logger = build_logger()
        attach_ui_handler(self.logger, self.append_log)

        self.scanned_data: Dict[str, List[MaterialRecord]] = {}
        self.checkbox_vars: Dict[str, tk.IntVar] = {}
        self.checkbox_widgets = {}
        self.running = False
        self.start_time = 0.0

        ctk.set_appearance_mode(self.app_config.theme)
        ctk.set_default_color_theme("blue")

        self.title("Eagle Exporter v1")
        self.geometry("920x840")
        self.minsize(780, 720)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_tabs()
        self._build_bottom_bar()
        self._load_config_into_ui()

    # ---------- UI Construction ----------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(15, 0), sticky="ew")
        ctk.CTkLabel(
            header,
            text="Eagle 数据自动化导出工具",
            font=ctk.CTkFont(family="Microsoft YaHei", size=24, weight="bold"),
        ).pack(side="left")

    def _build_tabs(self) -> None:
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

        self.tab_config = self.tabview.add("⚙️ 1. 基础配置与日志")
        self.tab_data = self.tabview.add("📦 2. 数据集选择")
        self.tab_settings = self.tabview.add("🔧 3. 偏好设置")

        self.tab_config.grid_columnconfigure(0, weight=1)
        self.tab_config.grid_rowconfigure(1, weight=1)
        self.tab_data.grid_columnconfigure(0, weight=1)
        self.tab_data.grid_rowconfigure(1, weight=1)

        self._build_config_tab()
        self._build_data_tab()
        self._build_settings_tab()

    def _build_config_tab(self) -> None:
        card = ctk.CTkFrame(self.tab_config, corner_radius=10)
        card.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="资源库路径:").grid(row=0, column=0, padx=(20, 10), pady=(15, 10), sticky="e")
        self.path_var = ctk.StringVar()
        self.path_entry = ctk.CTkEntry(card, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=1, padx=0, pady=(15, 10), sticky="ew")
        self.browse_btn = ctk.CTkButton(card, text="浏览...", width=80, command=self.browse_folder)
        self.browse_btn.grid(row=0, column=2, padx=(10, 20), pady=(15, 10))

        ctk.CTkLabel(card, text="保存至目录:").grid(row=1, column=0, padx=(20, 10), pady=(0, 10), sticky="e")
        self.save_path_var = ctk.StringVar()
        self.save_path_entry = ctk.CTkEntry(card, textvariable=self.save_path_var)
        self.save_path_entry.grid(row=1, column=1, padx=0, pady=(0, 10), sticky="ew")
        self.save_browse_btn = ctk.CTkButton(card, text="浏览...", width=80, command=self.browse_save_folder)
        self.save_browse_btn.grid(row=1, column=2, padx=(10, 20), pady=(0, 10))

        ctk.CTkLabel(card, text="并发线程:").grid(row=2, column=0, padx=(20, 10), pady=(0, 10), sticky="e")
        self.speed_slider = ctk.CTkSlider(card, from_=1, to=32, number_of_steps=31, command=self.update_slider_label)
        self.speed_slider.grid(row=2, column=1, padx=0, pady=(0, 10), sticky="ew")
        self.speed_label = ctk.CTkLabel(card, text="8 线程", width=80)
        self.speed_label.grid(row=2, column=2, padx=(10, 20), pady=(0, 10))

        ctk.CTkLabel(card, text="导出格式:").grid(row=3, column=0, padx=(20, 10), pady=(0, 15), sticky="ne")
        export_box = ctk.CTkFrame(card, fg_color="transparent")
        export_box.grid(row=3, column=1, columnspan=2, padx=(0, 20), pady=(0, 15), sticky="w")
        self.export_excel_var = ctk.BooleanVar(value=True)
        self.export_markdown_var = ctk.BooleanVar(value=True)
        self.export_json_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(export_box, text="Excel", variable=self.export_excel_var).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(export_box, text="Markdown", variable=self.export_markdown_var).pack(side="left", padx=(0, 12))
        ctk.CTkCheckBox(export_box, text="JSON", variable=self.export_json_var).pack(side="left")

        self.log_textbox = ctk.CTkTextbox(self.tab_config, corner_radius=10, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.log_textbox.insert("0.0", "[SYSTEM] Eagle Exporter 已就绪。\n")
        self.log_textbox.configure(state="disabled")

    def _build_data_tab(self) -> None:
        header = ctk.CTkFrame(self.tab_data, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text="已发现的数据集:", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.filter_datasets)
        self.search_entry = ctk.CTkEntry(header, textvariable=self.search_var, placeholder_text="🔍 搜索过滤数据集...", width=180)
        self.search_entry.pack(side="left", padx=20)
        self.search_entry.configure(state="disabled")

        self.select_all_var = ctk.IntVar(value=1)
        self.select_all_cb = ctk.CTkCheckBox(header, text="全选当前", variable=self.select_all_var, command=self.toggle_all_datasets)
        self.select_all_cb.pack(side="right", padx=10)
        self.select_all_cb.configure(state="disabled")

        self.dataset_scroll = ctk.CTkScrollableFrame(self.tab_data, corner_radius=10)
        self.dataset_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.dataset_scroll.grid_columnconfigure((0, 1), weight=1)

    def _build_settings_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_settings, corner_radius=10)
        frame.pack(fill="x", padx=20, pady=20)

        theme_row = ctk.CTkFrame(frame, fg_color="transparent")
        theme_row.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(theme_row, text="🎨 界面显示风格：", font=ctk.CTkFont(size=14)).pack(side="left")
        self.theme_menu = ctk.CTkOptionMenu(theme_row, values=["Light", "Dark"], command=self.change_theme, width=120)
        self.theme_menu.pack(side="right")

        toast_row = ctk.CTkFrame(frame, fg_color="transparent")
        toast_row.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(toast_row, text="🔔 任务完成弹窗提醒：", font=ctk.CTkFont(size=14)).pack(side="left")
        self.enable_toast_var = ctk.BooleanVar(value=True)
        self.toast_switch = ctk.CTkSwitch(toast_row, text="开启 / 关闭", variable=self.enable_toast_var, command=self.save_config)
        self.toast_switch.pack(side="right")

    def _build_bottom_bar(self) -> None:
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)

        prog = ctk.CTkFrame(bottom, fg_color="transparent")
        prog.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        prog.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(prog, height=12, corner_radius=6)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_bar.set(0)
        self.pct_label = ctk.CTkLabel(prog, text="💤 等待就绪", width=90, anchor="w")
        self.pct_label.grid(row=0, column=1, padx=(15, 0))

        self.scan_btn = ctk.CTkButton(bottom, text="1. 扫描与分析资源库", height=45, fg_color="#4B5563", hover_color="#374151", command=self.start_scanning)
        self.scan_btn.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        self.export_btn = ctk.CTkButton(bottom, text="2. 批量导出文件", height=45, fg_color="#2563EB", hover_color="#1D4ED8", command=self.start_exporting)
        self.export_btn.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        self.export_btn.configure(state="disabled")

    # ---------- Config & Logging ----------
    def _load_config_into_ui(self) -> None:
        self.path_var.set(self.app_config.library_path)
        self.save_path_var.set(self.app_config.save_path)
        self.enable_toast_var.set(self.app_config.enable_toast)
        self.theme_menu.set(self.app_config.theme)
        self.speed_slider.set(min(max(self.app_config.worker_count, 1), 32))
        self.update_slider_label(self.speed_slider.get())
        self.export_excel_var.set(self.app_config.export_excel)
        self.export_markdown_var.set(self.app_config.export_markdown)
        self.export_json_var.set(self.app_config.export_json)

    def append_log(self, text: str) -> None:
        self.after(0, self._append_log_safe, text)

    def _append_log_safe(self, text: str) -> None:
        try:
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", text)
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def save_config(self) -> None:
        self.app_config.library_path = self.path_var.get().strip()
        self.app_config.save_path = self.save_path_var.get().strip()
        self.app_config.enable_toast = self.enable_toast_var.get()
        self.app_config.theme = self.theme_menu.get()
        self.app_config.worker_count = int(self.speed_slider.get())
        self.app_config.export_excel = self.export_excel_var.get()
        self.app_config.export_markdown = self.export_markdown_var.get()
        self.app_config.export_json = self.export_json_var.get()
        self.config_manager.save(self.app_config)

    # ---------- UI Actions ----------
    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择 Eagle .library 文件夹")
        if folder:
            self.path_var.set(os.path.normpath(folder))
            self.save_config()

    def browse_save_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择数据导出保存目录")
        if folder:
            self.save_path_var.set(os.path.normpath(folder))
            self.save_config()

    def change_theme(self, new_theme: str) -> None:
        ctk.set_appearance_mode(new_theme)
        self.save_config()

    def update_slider_label(self, value) -> None:
        self.speed_label.configure(text=f"{int(float(value))} 线程")

    def update_progress(self, current: int, total: int) -> None:
        if total > 0:
            self.after(0, self._set_progress_ui, current / total)

    def _set_progress_ui(self, pct: float) -> None:
        self.progress_bar.set(pct)
        self.pct_label.configure(text=f"⚡ 处理中 {int(pct * 100)}%")

    def filter_datasets(self, *_args) -> None:
        query = self.search_var.get().lower()
        visible_count = 0
        for folder_name, cb in self.checkbox_widgets.items():
            if query in folder_name.lower():
                cb.grid(row=visible_count // 2, column=visible_count % 2, sticky="w", padx=10, pady=8)
                visible_count += 1
            else:
                cb.grid_remove()

    def toggle_all_datasets(self) -> None:
        value = self.select_all_var.get()
        query = self.search_var.get().lower()
        for folder_name, var in self.checkbox_vars.items():
            if query in folder_name.lower():
                var.set(value)

    def check_individual(self) -> None:
        query = self.search_var.get().lower()
        visible = [var.get() for name, var in self.checkbox_vars.items() if query in name.lower()]
        self.select_all_var.set(1 if visible and all(v == 1 for v in visible) else 0)

    # ---------- Task Flow ----------
    def start_scanning(self) -> None:
        target_dir = self.path_var.get().strip()
        if not target_dir or not os.path.exists(target_dir):
            messagebox.showwarning("无效路径", "请选择正确的 Eagle 资源库路径。")
            return

        self.save_config()
        self._lock_ui_for_task("引擎全速扫描中...")
        self.tabview.set("⚙️ 1. 基础配置与日志")
        self.scanned_data.clear()
        self.checkbox_vars.clear()
        self.checkbox_widgets.clear()
        for widget in self.dataset_scroll.winfo_children():
            widget.destroy()

        self.start_time = time.time()
        threading.Thread(target=self.scan_task, args=(target_dir,), daemon=True).start()

    def scan_task(self, target_dir: str) -> None:
        try:
            scanner = EagleScanner(worker_count=int(self.speed_slider.get()))
            self.scanned_data, total = scanner.scan(target_dir, progress_callback=self.update_progress)
            elapsed = round(time.time() - self.start_time, 1)
            self.logger.info(f"扫描完成，用时 {elapsed} 秒，共分析 {total} 个素材目录。")
            self.after(0, self._populate_dataset_ui)
        except Exception as exc:
            self.logger.error(f"扫描发生异常: {exc}")
            self.logger.error(traceback.format_exc())
            self.after(0, self._unlock_ui)

    def _populate_dataset_ui(self) -> None:
        self._unlock_ui()
        if not self.scanned_data:
            self.logger.warning("未扫描到可导出的数据。")
            return

        self.search_entry.configure(state="normal")
        self.select_all_cb.configure(state="normal")
        self.select_all_var.set(1)
        self.export_btn.configure(state="normal")

        for index, (folder_name, data_list) in enumerate(self.scanned_data.items()):
            var = ctk.IntVar(value=1)
            self.checkbox_vars[folder_name] = var
            cb = ctk.CTkCheckBox(
                self.dataset_scroll,
                text=f"{folder_name} (共 {len(data_list)} 条)",
                variable=var,
                command=self.check_individual,
            )
            self.checkbox_widgets[folder_name] = cb
            cb.grid(row=index // 2, column=index % 2, sticky="w", padx=10, pady=8)

        self.tabview.set("📦 2. 数据集选择")

    def start_exporting(self) -> None:
        if not any([self.export_excel_var.get(), self.export_markdown_var.get(), self.export_json_var.get()]):
            messagebox.showinfo("提示", "请至少勾选一种导出格式。")
            return

        save_dir = self.save_path_var.get().strip() or self.path_var.get().strip()
        if not save_dir or not os.path.exists(save_dir):
            messagebox.showwarning("无效路径", "请选择有效的导出目录。")
            return

        selected = {
            name: self.scanned_data[name]
            for name, var in self.checkbox_vars.items()
            if var.get() == 1
        }
        if not selected:
            messagebox.showinfo("提示", "你没有勾选任何数据集哦！")
            return

        self.save_config()
        self._lock_ui_for_task("正在打包导出数据...")
        self.tabview.set("⚙️ 1. 基础配置与日志")
        threading.Thread(target=self.export_task, args=(selected, save_dir), daemon=True).start()

    def export_task(self, filtered_data: Dict[str, List[MaterialRecord]], save_dir: str) -> None:
        try:
            base_name = f"Eagle_素材导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            base_output_path = Path(save_dir) / base_name

            exporters = []
            if self.export_excel_var.get():
                exporters.append(ExcelExporter())
            if self.export_markdown_var.get():
                exporters.append(MarkdownExporter())
            if self.export_json_var.get():
                exporters.append(JsonExporter())

            manager = ExportManager(exporters)
            outputs = manager.export_all(filtered_data, base_output_path)
            self.logger.info(f"导出成功，共生成 {len(outputs)} 个文件。")
            for file_path in outputs:
                self.logger.info(f"文件已生成：{file_path}")

            if self.enable_toast_var.get():
                self.after(
                    0,
                    lambda: ToastNotification(self, "导出成功", f"成功导出了 {len(filtered_data)} 个数据集。", save_dir),
                )
        except Exception as exc:
            self.logger.error(f"导出发生异常: {exc}")
            self.logger.error(traceback.format_exc())
        finally:
            self.after(0, self._unlock_ui)

    # ---------- State ----------
    def _lock_ui_for_task(self, button_text: str) -> None:
        self.running = True
        for btn in (self.scan_btn, self.export_btn, self.browse_btn, self.save_browse_btn):
            btn.configure(state="disabled")
        self.scan_btn.configure(text=button_text)
        self.speed_slider.configure(state="disabled")
        self.search_entry.configure(state="disabled")
        self.select_all_cb.configure(state="disabled")
        self.progress_bar.set(0)
        self.pct_label.configure(text="⏳ 处理中 0%")

    def _unlock_ui(self) -> None:
        self.running = False
        self.scan_btn.configure(state="normal", text="1. 扫描与分析资源库")
        self.browse_btn.configure(state="normal")
        self.save_browse_btn.configure(state="normal")
        self.speed_slider.configure(state="normal")
        if self.scanned_data:
            self.export_btn.configure(state="normal")
            self.search_entry.configure(state="normal")
            self.select_all_cb.configure(state="normal")
        self.progress_bar.set(1)
        self.pct_label.configure(text="✅ 任务完成")
        self.after(3000, self.reset_progress_state)

    def reset_progress_state(self) -> None:
        if not self.running:
            self.progress_bar.set(0)
            self.pct_label.configure(text="💤 等待就绪")

    def on_close(self) -> None:
        if self.running and not messagebox.askokcancel("警告", "后台任务正在运行中，确定退出吗？"):
            return
        self.save_config()
        self.destroy()
