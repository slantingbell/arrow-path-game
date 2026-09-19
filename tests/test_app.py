"""作业要求的 T01–T06 自动化测试。

这些测试不直接调用 game.Game，而是通过 main.ArrowPathApp 用**模拟鼠标点击**
走完整流程（坐标换算 → 点击分发 → 规则判定 → 界面状态切换），
因此同时覆盖了逻辑与界面两部分。

通过 SDL 的 dummy 视频驱动在无显示设备的环境下运行，无需人工操作。
运行：python -m unittest discover -s tests -t .
"""

from __future__ import annotations

import os
import unittest

# 必须在导入 pygame / main 之前设置，让 SDL 使用无头驱动。
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import Board, ClickKind  # noqa: E402
from levels import LEVELS  # noqa: E402
from main import (  # noqa: E402
    LOGICAL_H,
    LOGICAL_W,
    MAX_CELL,
    MAX_ZOOM,
    MIN_SIZE,
    MIN_ZOOM,
    ArrowPathApp,
    Screen,
)


def level(grid, max_mistakes=3, name="测试关"):
    return {"name": name, "grid": grid, "max_mistakes": max_mistakes}


# 所有箭头一开始就能飞出（且都位于边缘、朝向棋盘外）——用于 T01 / T03
OUTWARD_LEVEL = level(["U.U", "L.R", "D.D"], name="全部可飞出")

# R(0,0) 被同行的 U(0,1) 挡住 —— 用于 T02 / T05 / T06
BLOCKED_LEVEL = level(["RU..", "...D", "..L."], name="存在阻挡")


class AppTestCase(unittest.TestCase):
    """公共夹具：创建一个无头运行的游戏应用。"""

    levels: list[dict]

    def setUp(self):
        self.app = ArrowPathApp(self.levels, sound=False, save_path=None)

    def tearDown(self):
        pygame.quit()

    # ---- 辅助方法 ----

    def start_playing(self):
        """点"开始游戏"按钮，从开始界面进入游戏界面。"""
        self.app.click(self.app.menu_button_rect().center)
        assert self.app.screen_state is Screen.PLAYING

    def click_cell(self, row, col):
        """把棋盘坐标换算成像素坐标后点击，并推进一帧动画。"""
        kind = self.app.click(self.app.cell_center(row, col))
        self.app.update(0.016)
        return kind

    def click_primary(self):
        """点击结果界面上的主按钮。"""
        self.app.click(self.app.primary_button_rect().center)
        self.app.update(0.016)

    def clear_board(self):
        """按求解顺序点掉当前关卡的全部箭头。"""
        order = self.app.game.solve_order()
        self.assertIsNotNone(order, "关卡应当可解")
        for arrow in order:
            self.click_cell(arrow.row, arrow.col)


class TestT01ClearArrow(AppTestCase):
    """T01 点击前方无阻挡的箭头 —— 箭头飞出棋盘并消失。"""

    levels = [level(["..R..", "....."])]

    def test_t01_arrow_flies_out_and_disappears(self):
        self.start_playing()
        self.assertEqual(self.app.game.board.remaining, 1)

        kind = self.click_cell(0, 2)

        self.assertIs(kind, ClickKind.FLY_OUT)
        self.assertEqual(self.app.game.board.remaining, 0, "箭头应被消除")
        self.assertIsNone(self.app.game.board.arrow_at(0, 2))
        self.assertEqual(self.app.game.mistakes_left, 3, "飞出不应消耗失误")

    def test_t01_registers_fly_animation(self):
        self.start_playing()
        self.click_cell(0, 2)
        self.assertEqual(len(self.app.fly_anims), 1, "应登记一个飞出动画")

    def test_t01_animation_finishes_and_drains(self):
        self.start_playing()
        self.click_cell(0, 2)
        self.app.update(1.0)          # 推进足够长时间
        self.assertFalse(self.app.busy, "动画应播放完毕并被清空")


class TestT02BlockedArrow(AppTestCase):
    """T02 点击前方有阻挡的箭头 —— 箭头不消失，失误次数减 1。"""

    levels = [BLOCKED_LEVEL]

    def test_t02_arrow_stays_and_mistake_decreases(self):
        self.start_playing()
        before = self.app.game.board.remaining

        kind = self.click_cell(0, 0)   # R 被同行的 U 挡住

        self.assertIs(kind, ClickKind.BLOCKED)
        self.assertEqual(self.app.game.board.remaining, before, "箭头不应消失")
        self.assertIsNotNone(self.app.game.board.arrow_at(0, 0))
        self.assertEqual(self.app.game.mistakes_left, 2, "失误次数应减 1")

    def test_t02_registers_shake_animation(self):
        self.start_playing()
        self.click_cell(0, 0)
        self.assertEqual(len(self.app.shake_anims), 1, "应登记一个碰撞动画")

    def test_t02_repeated_clicks_keep_decreasing(self):
        self.start_playing()
        self.click_cell(0, 0)
        self.click_cell(0, 0)
        self.assertEqual(self.app.game.mistakes_left, 1)


class TestT03Boundary(AppTestCase):
    """T03 点击位于边缘且朝向棋盘外的箭头 —— 正常消失，不发生越界错误。"""

    levels = [OUTWARD_LEVEL]

    def test_t03_all_edge_outward_arrows_fly_out_without_index_error(self):
        self.start_playing()
        board = self.app.game.board
        edge_arrows = [
            a for a in board.arrows
            if a.row in (0, board.rows - 1) or a.col in (0, board.cols - 1)
        ]
        self.assertTrue(edge_arrows, "测试关卡应包含边缘箭头")

        for arrow in edge_arrows:
            with self.subTest(arrow=str(arrow)):
                # 这里是本测试的关键：任何越界都会以 IndexError 暴露出来
                kind = self.click_cell(arrow.row, arrow.col)
                self.assertIs(kind, ClickKind.FLY_OUT)

    def test_t03_every_cell_every_direction_click_is_safe(self):
        """逐个格子、逐个方向点击，确认不会抛 IndexError。"""
        for symbol in "UDLR":
            with self.subTest(direction=symbol):
                grid = [["."] * 3 for _ in range(3)]
                grid[0][0] = symbol        # 左上角
                app = ArrowPathApp(
                    [level(["".join(r) for r in grid])], sound=False, save_path=None
                )
                try:
                    app.click(app.menu_button_rect().center)
                    app.click(app.cell_center(0, 0))
                finally:
                    pygame.quit()

    def test_t03_clearing_all_edge_arrows_clears_level(self):
        self.start_playing()
        self.clear_board()
        self.assertEqual(self.app.game.board.remaining, 0)


class TestT04LevelCleared(AppTestCase):
    """T04 消除本关全部箭头 —— 显示通关并进入下一关。"""

    levels = [
        level(["..R.."], name="第一关"),
        level(["U...."], name="第二关"),
    ]

    def test_t04_shows_cleared_then_advances(self):
        self.start_playing()
        self.assertEqual(self.app.game.level_number, 1)

        self.clear_board()
        self.assertIs(self.app.screen_state, Screen.LEVEL_CLEARED, "应显示通关界面")

        self.click_primary()
        self.assertIs(self.app.screen_state, Screen.PLAYING, "应进入下一关")
        self.assertEqual(self.app.game.level_number, 2, "关卡号应递增")
        self.assertEqual(self.app.game.board.remaining, 1, "新关卡应回到初始布局")
        self.assertEqual(self.app.game.mistakes_left, 3, "新关卡失误次数应重置")

    def test_t04_last_level_shows_all_cleared(self):
        self.start_playing()
        self.clear_board()
        self.click_primary()          # 进入第 2 关
        self.clear_board()            # 通关最后一关
        self.assertIs(self.app.screen_state, Screen.ALL_CLEARED)


class TestT05MistakesExhausted(AppTestCase):
    """T05 失误次数耗尽 —— 显示失败并允许重新开始。"""

    levels = [BLOCKED_LEVEL]

    def test_t05_shows_failure_when_mistakes_run_out(self):
        self.start_playing()
        max_mistakes = self.app.game.max_mistakes

        for _ in range(max_mistakes):
            self.click_cell(0, 0)     # 反复点击被阻挡的箭头

        self.assertEqual(self.app.game.mistakes_left, 0)
        self.assertIs(self.app.screen_state, Screen.FAILED, "应显示失败界面")

    def test_t05_restart_after_failure(self):
        self.start_playing()
        for _ in range(self.app.game.max_mistakes):
            self.click_cell(0, 0)
        self.assertIs(self.app.screen_state, Screen.FAILED)

        self.click_primary()          # 失败界面的"重新开始本关"
        self.assertIs(self.app.screen_state, Screen.PLAYING)
        self.assertEqual(self.app.game.mistakes_left, self.app.game.max_mistakes)
        self.assertEqual(self.app.game.board.remaining, 4)

    def test_t05_clicks_ignored_after_failure(self):
        self.start_playing()
        for _ in range(self.app.game.max_mistakes):
            self.click_cell(0, 0)
        board_before = self.app.game.board.to_grid()
        self.click_cell(0, 1)         # 失败后再点棋盘
        self.assertEqual(self.app.game.board.to_grid(), board_before)


class TestT06Restart(AppTestCase):
    """T06 游戏进行中重新开始 —— 箭头布局和失误次数恢复。"""

    levels = [BLOCKED_LEVEL]

    def test_t06_restart_button_restores_state(self):
        self.start_playing()
        initial = self.app.game.board.to_grid()

        self.click_cell(1, 3)         # 移除一个箭头
        self.click_cell(0, 0)         # 消耗一次失误
        self.assertNotEqual(self.app.game.board.to_grid(), initial)
        self.assertEqual(self.app.game.mistakes_left, 2)

        # 点击界面上的"重新开始"按钮
        self.app.click(self.app.restart_button_rect().center)

        self.assertEqual(self.app.game.board.to_grid(), initial, "布局应恢复")
        self.assertEqual(self.app.game.mistakes_left, 3, "失误次数应恢复")
        self.assertIs(self.app.screen_state, Screen.PLAYING)

    def test_t06_restart_clears_animations(self):
        self.start_playing()
        self.click_cell(1, 3)
        self.assertTrue(self.app.busy)
        self.app.click(self.app.restart_button_rect().center)
        self.assertFalse(self.app.busy, "重新开始应清空动画队列")

    def test_t06_restart_works_after_partial_progress(self):
        self.start_playing()
        initial = self.app.game.board.to_grid()
        for _ in range(3):
            self.click_cell(1, 3)     # 反复点已消失的格子（空格，无副作用）
        self.app.click(self.app.restart_button_rect().center)
        self.assertEqual(self.app.game.board.to_grid(), initial)


class TestInterface(AppTestCase):
    """界面层面的补充检查。"""

    levels = [BLOCKED_LEVEL, OUTWARD_LEVEL]

    def test_starts_on_menu(self):
        self.assertIs(self.app.screen_state, Screen.MENU)

    def test_click_on_menu_enters_game(self):
        self.start_playing()
        self.assertEqual(self.app.game.level_number, 1)
        self.assertEqual(self.app.game.mistakes_left, self.app.game.max_mistakes)

    def test_click_outside_board_does_nothing(self):
        self.start_playing()
        before = self.app.game.board.to_grid()
        kind = self.app.click((3, 3))     # 左上角空白区域
        self.assertIsNone(kind)
        self.assertEqual(self.app.game.board.to_grid(), before)

    def test_hud_reports_current_values(self):
        """游戏界面所需的信息都能从模型取到。"""
        self.start_playing()
        self.assertEqual(self.app.game.level_name, "存在阻挡")
        self.assertEqual(self.app.game.board.remaining, 4)
        self.assertEqual(self.app.game.mistakes_left, 3)
        self.assertEqual(self.app.game.level_number, 1)
        self.assertEqual(self.app.game.total_levels, 2)

    def test_cell_at_is_inverse_of_cell_center(self):
        self.start_playing()
        board = self.app.game.board
        for row in range(board.rows):
            for col in range(board.cols):
                with self.subTest(cell=(row, col)):
                    self.assertEqual(
                        self.app.cell_at(self.app.cell_center(row, col)), (row, col)
                    )

    def test_cell_at_returns_none_outside_board(self):
        self.start_playing()
        self.assertIsNone(self.app.cell_at((0, 0)))
        self.assertIsNone(self.app.cell_at((10, 10)))

    def test_draw_does_not_crash_on_every_screen(self):
        """五种界面都能正常渲染。"""
        self.app.draw()                                  # 开始界面
        self.start_playing()
        self.app.draw()                                  # 游戏界面
        self.click_cell(0, 0)                            # 触发碰撞动画
        self.app.draw()
        self.clear_board()
        self.app.draw()                                  # 通关界面

        app = ArrowPathApp([level(["..R.."])], sound=False, save_path=None)
        try:
            app.click(app.menu_button_rect().center)
            app.click(app.cell_center(0, 2))
            app.draw()                                   # 全部通关界面
        finally:
            pygame.quit()

    def test_font_cache_survives_pygame_restart(self):
        """回归测试：pygame.quit() 会让缓存中的 Font 失效。

        曾经的现象是第二次创建应用并绘制时抛
        "Invalid font (font module quit since font created)"。
        """
        for _ in range(3):
            app = ArrowPathApp([level(["..R.."])], sound=False, save_path=None)
            try:
                app.draw()          # 开始界面
                app.click(app.menu_button_rect().center)
                app.draw()          # 游戏界面（需要中文文字）
                app.click(app.cell_center(0, 2))
                app.draw()          # 通关界面
            finally:
                pygame.quit()

    def test_load_font_returns_usable_font_after_quit(self):
        from main import load_font

        pygame.quit()
        font = load_font(24)
        self.assertIsNotNone(font.render("一箭又一箭", True, (0, 0, 0)))

    def test_all_shipped_boards_fit_in_canvas(self):
        """每个关卡的棋盘都必须完整落在画布内。

        格子边长固定为 96 时，7x7 棋盘会高到 928 像素、超出 830 的画布，
        超出部分的格子仍是合法坐标，但点击会被"越界"判断挡掉，
        表现为关卡永远清不完。这里逐格确认棋盘没有溢出。
        """
        for lv in LEVELS:
            with self.subTest(level=lv["name"]):
                app = ArrowPathApp([lv], sound=False, save_path=None)
                try:
                    app.click(app.menu_button_rect().center)
                    board = app.game.board
                    self.assertLessEqual(app.cell_size(), MAX_CELL)
                    for r in range(board.rows):
                        for c in range(board.cols):
                            rect = app.cell_rect(r, c)
                            self.assertGreaterEqual(rect.left, 0)
                            self.assertGreaterEqual(rect.top, 0)
                            self.assertLessEqual(rect.right, LOGICAL_W)
                            self.assertLessEqual(rect.bottom, LOGICAL_H)
                finally:
                    pygame.quit()

    def test_larger_boards_use_smaller_cells(self):
        """棋盘越大，格子越小，但仍保持在可点击的尺寸。"""
        sizes = []
        for lv in LEVELS:
            app = ArrowPathApp([lv], sound=False, save_path=None)
            try:
                app.click(app.menu_button_rect().center)
                sizes.append((app.game.board.rows, app.cell_size()))
            finally:
                pygame.quit()
        for rows, cell in sizes:
            self.assertGreaterEqual(cell, 28, f"{rows} 行的棋盘格子太小了")

    def test_levels_are_solvable_from_shipped_data(self):
        """用真实关卡数据跑一遍完整流程。"""
        app = ArrowPathApp(LEVELS, sound=False, save_path=None)
        try:
            app.click(app.menu_button_rect().center)
            for _ in range(len(LEVELS)):
                order = app.game.solve_order()
                self.assertIsNotNone(order)
                for arrow in order:
                    app.click(app.cell_center(arrow.row, arrow.col))
                if app.screen_state is Screen.LEVEL_CLEARED:
                    app.click(app.primary_button_rect().center)
            self.assertIs(app.screen_state, Screen.ALL_CLEARED)
        finally:
            pygame.quit()


class TestMenuButtonOnly(AppTestCase):
    """开始界面只有点到"开始游戏"按钮才会进入游戏（修复误触缺陷）。"""

    levels = [level(["..R.."])]

    def test_start_button_enters_game(self):
        self.start_playing()

    def test_clicking_title_does_not_start(self):
        self.app.click((LOGICAL_W // 2, 150))      # 标题文字
        self.assertIs(self.app.screen_state, Screen.MENU)

    def test_clicking_rule_card_does_not_start(self):
        self.app.click((LOGICAL_W // 2, 350))      # 规则说明卡片
        self.assertIs(self.app.screen_state, Screen.MENU)

    def test_clicking_blank_areas_does_not_start(self):
        for pos in [(10, 10), (10, LOGICAL_H - 10), (LOGICAL_W - 10, 10), (30, 700)]:
            with self.subTest(pos=pos):
                self.app.click(pos)
                self.assertIs(self.app.screen_state, Screen.MENU)

    def test_near_miss_clicks_just_outside_button_do_not_start(self):
        rect = self.app.menu_button_rect()
        for pos in [
            (rect.left - 2, rect.centery),
            (rect.right + 2, rect.centery),
            (rect.centerx, rect.top - 2),
            (rect.centerx, rect.bottom + 2),
        ]:
            with self.subTest(pos=pos):
                self.app.click(pos)
                self.assertIs(self.app.screen_state, Screen.MENU)


class TestResultButtonsOnly(AppTestCase):
    """通关 / 失败 / 全部通关界面也只有点主按钮才会继续。"""

    levels = [level(["..R.."], name="第一关"), level(["U...."], name="第二关")]

    def _clear_level(self):
        self.start_playing()
        self.clear_board()

    def test_result_screen_ignores_click_elsewhere(self):
        self._clear_level()
        self.assertIs(self.app.screen_state, Screen.LEVEL_CLEARED)
        for pos in [(20, 20), (LOGICAL_W // 2, 120), (LOGICAL_W - 20, LOGICAL_H - 20)]:
            with self.subTest(pos=pos):
                self.app.click(pos)
                self.assertIs(self.app.screen_state, Screen.LEVEL_CLEARED)
                self.assertEqual(self.app.game.level_number, 1, "不应跳到下一关")

    def test_failure_screen_ignores_click_elsewhere(self):
        app = ArrowPathApp([BLOCKED_LEVEL], sound=False, save_path=None)
        try:
            app.click(app.menu_button_rect().center)
            for _ in range(app.game.max_mistakes):
                app.click(app.cell_center(0, 0))
            self.assertIs(app.screen_state, Screen.FAILED)
            app.click((20, 20))
            self.assertIs(app.screen_state, Screen.FAILED, "不应因误点而重开")
        finally:
            pygame.quit()


class TestResizeAndZoom(AppTestCase):
    """窗口自由缩放：画面等比缩放，鼠标点击仍能正确换算。"""

    levels = [level(["..R..", "....."])]

    def test_default_window_maps_identity(self):
        _, scale = self.app.viewport()
        self.assertAlmostEqual(scale, 1.0)

    def test_resize_scales_viewport(self):
        self.app.resize((1440, 1660))
        view, scale = self.app.viewport()
        self.assertAlmostEqual(scale, 2.0)
        self.assertEqual(view.size, (1440, 1660))

    def test_click_hits_right_cell_after_resize(self):
        self.start_playing()
        self.app.resize((1440, 1660))            # 放大到 2 倍
        view, scale = self.app.viewport()
        lx, ly = self.app.cell_center(0, 2)
        self.app.click((view.x + lx * scale, view.y + ly * scale))
        self.assertEqual(self.app.game.board.remaining, 0, "缩放后点击仍应命中该箭头")

    def test_click_hits_right_cell_after_shrink(self):
        self.start_playing()
        self.app.resize((504, 581))              # 缩到 0.7 倍
        view, scale = self.app.viewport()
        self.assertLess(scale, 1.0)
        lx, ly = self.app.cell_center(0, 2)
        self.app.click((view.x + lx * scale, view.y + ly * scale))
        self.assertEqual(self.app.game.board.remaining, 0)

    def test_window_to_logical_roundtrip(self):
        for size in [(1440, 1660), (360, 415), (1000, 830), (720, 415)]:
            with self.subTest(size=size):
                self.app.resize(size)
                view, scale = self.app.viewport()
                for point in [
                    (view.x + 10, view.y + 10),
                    (view.centerx, view.centery),
                ]:
                    lx, ly = self.app.window_to_logical(point)
                    self.assertAlmostEqual(view.x + lx * scale, point[0], places=3)
                    self.assertAlmostEqual(view.y + ly * scale, point[1], places=3)

    def test_letterbox_keeps_aspect_ratio(self):
        """窗口比例与画布不一致时，画面保持等比并居中。"""
        self.app.resize((1440, 830))
        view, scale = self.app.viewport()
        self.assertGreater(view.x, 0, "应出现左右留白")
        self.assertAlmostEqual(view.width / view.height, LOGICAL_W / LOGICAL_H, places=3)

    def test_click_in_letterbox_is_ignored(self):
        """留白区域上的点击应被忽略；按钮位置也必须按留白偏移换算。"""
        self.app.resize((1440, 830))
        view, _ = self.app.viewport()
        self.assertGreater(view.x, 0, "应出现左右留白")

        for pos in [(5, 400), (1435, 400), (5, 5), (1435, 825)]:
            with self.subTest(pos=pos):
                self.app.click(pos)              # 四角都在留白上
                self.assertIs(self.app.screen_state, Screen.MENU)

        # 按钮实际画在 view.x 之后，因此用未换算的画布坐标去点不应命中
        rect = self.app.menu_button_rect()
        self.app.click((rect.centerx, rect.centery))
        self.assertIs(self.app.screen_state, Screen.MENU, "未换算坐标不应命中按钮")

        # 换算后的正确位置则可以命中
        self.app.click((view.x + rect.centerx, view.y + rect.centery))
        self.assertIs(self.app.screen_state, Screen.PLAYING)

    def test_zoom_is_clamped(self):
        self.app.set_zoom(99.0)
        self.assertAlmostEqual(self.app.zoom, MAX_ZOOM)
        self.app.set_zoom(0.001)
        self.assertAlmostEqual(self.app.zoom, MIN_ZOOM)

    def test_zoom_changes_scale(self):
        self.app.set_zoom(2.0)
        _, scale = self.app.viewport()
        self.assertAlmostEqual(scale, 2.0)
        self.app.zoom_by(-0.5)
        _, scale = self.app.viewport()
        self.assertAlmostEqual(scale, 1.5)

    def test_resize_enforces_minimum_size(self):
        self.app.resize((10, 10))
        w, h = self.app.window.get_size()
        self.assertGreaterEqual(w, MIN_SIZE[0])
        self.assertGreaterEqual(h, MIN_SIZE[1])

    def test_draw_after_resize_and_zoom_does_not_crash(self):
        self.start_playing()
        for size, zoom in [((1200, 900), 1.0), ((400, 500), 2.5), ((1600, 900), 0.6)]:
            with self.subTest(size=size, zoom=zoom):
                self.app.resize(size)
                self.app.set_zoom(zoom)
                self.app.draw()


class TestLayout(AppTestCase):
    """界面元素不得互相重叠、也不得跑出画布。

    "文字压在按钮上""按钮跑到画布外"这类问题不会让程序报错，
    但会直接在画面上露馅，所以单独用一组用例盯住。
    """

    # 两关：清空第一关时状态是 LEVEL_CLEARED（而非最后一关的 ALL_CLEARED）
    levels = [level(["..R..", "....."], name="第一关"), level(["U...."], name="第二关")]

    def _all_screens(self):
        """逐个界面返回需要检查是否越界的矩形。"""
        self.start_playing()
        yield "playing", [
            self.app.restart_button_rect(),
            *(r for r, _l, _a in self.app.tool_buttons()),
            *(self.app.cell_rect(r, c)
              for r in range(self.app.game.board.rows)
              for c in range(self.app.game.board.cols)),
        ]

    def test_rects_stay_inside_canvas(self):
        for name, rects in self._all_screens():
            for rect in rects:
                with self.subTest(screen=name, rect=rect):
                    self.assertGreaterEqual(rect.left, 0)
                    self.assertGreaterEqual(rect.top, 0)
                    self.assertLessEqual(rect.right, LOGICAL_W)
                    self.assertLessEqual(rect.bottom, LOGICAL_H)

    def test_tool_buttons_do_not_overlap_board(self):
        """底部工具按钮不能压在棋盘上，任何关卡尺寸都不行。"""
        for lv in LEVELS:
            app = ArrowPathApp([lv], sound=False, save_path=None)
            try:
                app.click(app.menu_button_rect().center)
                board = app.game.board
                last = app.cell_rect(board.rows - 1, board.cols - 1)
                top = min(r.top for r, _l, _a in app.tool_buttons())
                with self.subTest(level=lv["name"]):
                    self.assertLess(
                        last.bottom, top,
                        f"{lv['name']} 的棋盘底部 {last.bottom} 压到了工具按钮 {top}",
                    )
            finally:
                pygame.quit()

    def test_tool_buttons_do_not_overlap_each_other(self):
        rects = [r for r, _l, _a in self.app.tool_buttons()]
        for i, first in enumerate(rects):
            for second in rects[i + 1:]:
                with self.subTest(pair=(i,)):
                    self.assertFalse(first.colliderect(second))

    def test_result_panel_fits_and_button_clears_detail_text(self):
        """结果面板：按钮不能和上面的得分文字叠在一起。"""
        self.start_playing()
        self.clear_board()
        self.assertIs(self.app.screen_state, Screen.LEVEL_CLEARED)

        panel = self.app.result_panel_rect()
        button = self.app.primary_button_rect()

        self.assertGreaterEqual(panel.left, 0)
        self.assertLessEqual(panel.right, LOGICAL_W)
        self.assertLessEqual(panel.bottom, LOGICAL_H)
        self.assertTrue(panel.contains(button), "主按钮应在面板内")
        # 面板里文字约到 top+134，按钮必须明显低于它
        self.assertGreater(
            button.top - (panel.top + 134), 20,
            "按钮与得分文字间距过小，会叠在一起",
        )

    def test_level_select_buttons_do_not_overlap(self):
        app = ArrowPathApp(LEVELS, sound=False, save_path=None)
        try:
            buttons = app.level_buttons()
            self.assertEqual(len(buttons), len(LEVELS))
            for i, (first, _) in enumerate(buttons):
                for second, _ in buttons[i + 1:]:
                    self.assertFalse(first.colliderect(second))
                self.assertGreaterEqual(first.left, 0)
                self.assertLessEqual(first.right, LOGICAL_W)
            back = app.back_button_rect()
            self.assertGreater(
                back.top, max(r.bottom for r, _ in buttons),
                "返回按钮不应压住关卡按钮",
            )
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
