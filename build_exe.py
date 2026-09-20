"""把游戏打包成单文件可执行程序（附加功能）。

用法：
    python build_exe.py            # 打包
    python build_exe.py --clean    # 打包前先清掉上次的产物

产物在 dist/ 目录下：
    Windows  dist/一箭又一箭.exe
    macOS    dist/一箭又一箭
    其他     dist/arrow-path-game

需要先安装 PyInstaller：
    pip install pyinstaller

说明：
- 使用 --onefile 打包成单个文件，方便直接发给别人运行，
  代价是启动时要先把内容解包到临时目录，首次启动略慢。
- 使用 --windowed 不弹控制台窗口；相应地，运行期异常不会打印到屏幕上，
  调试时请直接运行 python main.py。
- 存档位置已由 storage._default_save_path() 处理：打包后存档放在
  可执行文件同目录，而不是临时解包目录。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

APP_NAME = "一箭又一箭" if sys.platform == "win32" else "arrow-path-game"
ENTRY = PROJECT_ROOT / "main.py"


def clean() -> None:
    """删除上一次的打包产物。"""
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
            print(f"已删除 {path.relative_to(PROJECT_ROOT)}")
    spec = PROJECT_ROOT / f"{APP_NAME}.spec"
    if spec.exists():
        spec.unlink()


def ensure_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("未安装 PyInstaller，请先执行：pip install pyinstaller")
        return False
    return True


def build() -> int:
    if not ensure_pyinstaller():
        return 1

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        # 这些是开发与测试用的模块，打包时不需要
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
        "--exclude-module", "test",
        "--exclude-module", "tkinter",
        str(ENTRY),
    ]

    print("执行:", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print("打包失败")
        return result.returncode

    target = DIST_DIR / (f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME)
    if target.exists():
        size_mb = target.stat().st_size / 1024 / 1024
        print(f"\n打包完成：{target.relative_to(PROJECT_ROOT)}（{size_mb:.1f} MB）")
    return 0


def main() -> int:
    if "--clean" in sys.argv:
        clean()
    return build()


if __name__ == "__main__":
    sys.exit(main())
