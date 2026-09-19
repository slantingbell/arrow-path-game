"""生成 README 用的界面截图。

直接驱动真实的 ArrowPathApp 渲染，并把画面保存为 PNG，
因此截图与实际运行效果一致，无需人工截屏。

运行：
    python tools/capture_screens.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 无头渲染，脚本在无显示设备的机器上也能跑。
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pygame  # noqa: E402

from main import ArrowPathApp, Screen  # noqa: E402

OUT_DIR = PROJECT_ROOT / "docs" / "screenshots"


def save(app: ArrowPathApp, name: str) -> None:
    app.draw()
    path = OUT_DIR / name
    pygame.image.save(app.screen, str(path))
    print(f"已保存 {path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 开始界面 ----
    app = ArrowPathApp()
    save(app, "01-menu.png")

    # ---- 游戏界面：第 3 关，已消掉几个箭头，并触发一次碰撞反馈 ----
    app.click((5, 5))               # 进入第 1 关
    app.game.level_index = 2        # 切到第 3 关（左右对称，画面最好看）
    app.game.restart()
    app.screen_state = Screen.PLAYING

    order = app.game.solve_order() or []
    for arrow in order[:3]:         # 先飞掉 3 个箭头
        app.click(app.cell_center(arrow.row, arrow.col))
        app.update(1.0)             # 让飞出动画播完

    # 故意点一个被阻挡的箭头，定格在晃动 + 变红的瞬间
    blocked = [a for a in app.game.board.arrows if not app.game.board.is_path_clear(a)]
    if blocked:
        target = blocked[0]
        app.click(app.cell_center(target.row, target.col))
        app.update(0.12)            # 只推进一小段，保留碰撞反馈
    save(app, "02-playing.png")

    # ---- 本关通关界面：用第 2 关（不是最后一关）才会出现"进入下一关" ----
    app.game.level_index = 1
    app.restart_level()
    for arrow in app.game.solve_order() or []:
        app.click(app.cell_center(arrow.row, arrow.col))
        app.update(1.0)             # 逐个等动画播完，画面干净
    app.update(1.0)
    assert app.screen_state is Screen.LEVEL_CLEARED, app.screen_state
    save(app, "03-level-cleared.png")

    # ---- 全部通关界面：第 3 关是最后一关 ----
    app.advance_level()
    for arrow in app.game.solve_order() or []:
        app.click(app.cell_center(arrow.row, arrow.col))
        app.update(1.0)
    app.update(1.0)
    assert app.screen_state is Screen.ALL_CLEARED, app.screen_state
    save(app, "05-all-cleared.png")

    # ---- 失败界面：在第 1 关反复点被阻挡的箭头，直到失误耗尽 ----
    app.game.level_index = 0
    app.game.restart()
    app.screen_state = Screen.PLAYING
    while app.screen_state is Screen.PLAYING:
        blocked = [
            a for a in app.game.board.arrows if not app.game.board.is_path_clear(a)
        ]
        if not blocked:
            break
        app.click(app.cell_center(blocked[0].row, blocked[0].col))
        app.update(1.0)
    assert app.screen_state is Screen.FAILED, app.screen_state
    save(app, "04-failed.png")

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
