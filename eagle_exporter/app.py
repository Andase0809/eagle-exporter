from __future__ import annotations

import argparse
import importlib
import subprocess
from pathlib import Path

# Optional Windows DPI support
try:
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
NETFX_UI_EXE = BASE_DIR / "netfx_ui" / "EagleExporterFrontend.exe"


def ensure_dependencies() -> None:
    required = {
        "xlsxwriter": "xlsxwriter",
        "PIL": "pillow",
        "customtkinter": "customtkinter",
    }
    missing = []
    for module, pkg_name in required.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pkg_name)

    if not missing:
        return

    packages = " ".join(missing)
    raise RuntimeError(
        "缺少运行依赖："
        f"{packages}。请先运行 `python -m pip install -e .` "
        "或 `python -m pip install -r requirements.txt`。"
    )


def launch_netfx_frontend(exe_path: Path) -> bool:
    if not exe_path.exists():
        print(f"[WARN] 未找到 .NET 前端可执行文件: {exe_path}")
        return False

    try:
        subprocess.Popen([str(exe_path)])
        print(f"[INFO] 已启动 .NET 前端: {exe_path}")
        return True
    except Exception as exc:
        print(f"[ERROR] 启动 .NET 前端失败: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Eagle Exporter v1 启动器")
    parser.add_argument("--frontend", choices=["python", "netfx"], default="python")
    parser.add_argument("--netfx-exe", default=str(NETFX_UI_EXE))
    args = parser.parse_args()

    if args.frontend == "netfx":
        if launch_netfx_frontend(Path(args.netfx_exe)):
            return 0
        print("[WARN] 回退到 Python 前端。")

    ensure_dependencies()

    from eagle_exporter.ui.main_window import EagleExporterApp

    app = EagleExporterApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
