"""附加功能的自动化测试。

覆盖 PRD 第 5.5 节列出的可选功能：
更多关卡 / 关卡选择、随机关卡生成、提示、撤销、计时计分星级、
自动求解、音效、进度存档。

运行：python -m unittest discover -s tests -t .
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import storage  # noqa: E402
from audio import SoundBank  # noqa: E402
from game import Board, Game, GameStatus, greedy_clearable  # noqa: E402
from generator import (  # noqa: E402
    generate_grid,
    generate_level,
    max_mistakes_for,
    random_level,
)
from levels import LEVELS, validate_levels  # noqa: E402
from main import ArrowPathApp, Screen  # noqa: E402


class TempSaveMixin:
    """为每个用例准备一个临时目录，避免碰到本机的真实存档。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self._tmp.name) / "save.json"

    def tearDown(self):
        self._tmp.cleanup()


class TestGenerator(unittest.TestCase):
    """附加功能：随机生成可通关的关卡。"""

    def test_generated_levels_are_always_solvable(self):
        """逆序放置构造的可通关性是硬保证，多种尺寸都要成立。"""
        for rows, cols, n in [(4, 4, 6), (5, 5, 9), (5, 5, 12), (6, 6, 14), (7, 7, 18)]:
            for seed in range(6):
                with self.subTest(size=(rows, cols), seed=seed):
                    grid = generate_grid(rows, cols, n, __import__("random").Random(seed))
                    board = Board.from_grid(grid)
                    self.assertEqual(board.remaining, n)
                    self.assertTrue(
                        greedy_clearable(board),
                        f"{rows}x{cols} seed={seed} 生成的关卡无法通关",
                    )

    def test_generated_level_passes_validation(self):
        for difficulty in range(1, 6):
            with self.subTest(difficulty=difficulty):
                validate_levels([random_level(seed=difficulty, difficulty=difficulty)])

    def test_same_seed_gives_same_level(self):
        first = generate_level(5, 5, 10, seed=123)
        second = generate_level(5, 5, 10, seed=123)
        self.assertEqual(first["grid"], second["grid"], "同一种子应当可复现")

    def test_different_seeds_give_different_levels(self):
        grids = {tuple(generate_level(6, 6, 14, seed=s)["grid"]) for s in range(10)}
        self.assertGreater(len(grids), 1, "不同种子不应总是给出同一布局")

    def test_generated_level_has_required_fields(self):
        lv = generate_level(5, 5, 8, seed=1, name="自定义")
        self.assertEqual(lv["name"], "自定义")
        self.assertTrue(lv["generated"])
        self.assertGreaterEqual(lv["max_mistakes"], 1)

    def test_higher_difficulty_means_bigger_board(self):
        easy = Board.from_grid(random_level(seed=1, difficulty=1)["grid"])
        hard = Board.from_grid(random_level(seed=1, difficulty=5)["grid"])
        self.assertGreater(hard.remaining, easy.remaining)

    def test_max_mistakes_scales_with_arrow_count(self):
        self.assertLessEqual(max_mistakes_for(6), max_mistakes_for(18))
        self.assertGreaterEqual(max_mistakes_for(6), 1)

    def test_impossible_request_raises(self):
        """1x1 的棋盘放不下 5 个箭头，应当明确报错而不是返回残缺关卡。"""
        with self.assertRaises(ValueError):
            generate_grid(1, 1, 5)


class TestStorage(TempSaveMixin, unittest.TestCase):
    """附加功能：保存游戏进度。"""

    def test_save_then_load_roundtrip(self):
        game = Game(LEVELS)
        game.level_index = 2
        game.restart()
        for arrow in (game.solve_order() or [])[:3]:
            game.click(arrow.row, arrow.col)

        self.assertTrue(storage.save_game(game, self.save_path))
        data = storage.load_save(self.save_path)
        self.assertIsNotNone(data)

        other = Game(LEVELS)
        self.assertTrue(other.restore(data))
        self.assertEqual(other.level_index, 2)
        self.assertEqual(other.board.to_grid(), game.board.to_grid())

    def test_missing_file_returns_none(self):
        self.assertIsNone(storage.load_save(self.save_path))
        self.assertFalse(storage.has_save(self.save_path))

    def test_corrupt_file_returns_none(self):
        self.save_path.write_text("{ 这不是合法的 JSON", encoding="utf-8")
        self.assertIsNone(storage.load_save(self.save_path))

    def test_wrong_version_rejected(self):
        self.save_path.write_text(json.dumps({"version": 999}), encoding="utf-8")
        self.assertIsNone(storage.load_save(self.save_path))

    def test_clear_removes_file(self):
        game = Game(LEVELS)
        storage.save_game(game, self.save_path)
        self.assertTrue(storage.has_save(self.save_path))
        storage.clear_save(self.save_path)
        self.assertFalse(storage.has_save(self.save_path))

    def test_describe_mentions_level_and_score(self):
        game = Game(LEVELS)
        game.level_index = 1
        game.restart()
        text = storage.describe(game.to_save())
        self.assertIn("第 2 关", text)

    def test_save_to_unwritable_path_returns_false(self):
        """存档失败不应抛异常，只是返回 False。"""
        bad = Path(self._tmp.name) / "no_such_dir" / "s.json"
        self.assertFalse(storage.save_game(Game(LEVELS), bad))


class TestAudio(unittest.TestCase):
    """附加功能：音效。"""

    def test_bank_builds_with_dummy_driver(self):
        pygame.mixer.quit()
        bank = SoundBank()
        self.assertTrue(bank.enabled, "dummy 音频驱动下应当能建立音效")
        pygame.mixer.quit()

    def test_disabled_bank_is_silent_noop(self):
        bank = SoundBank(enabled=False)
        self.assertFalse(bank.enabled)
        bank.play("fly")          # 不应抛异常

    def test_playing_unknown_effect_is_noop(self):
        pygame.mixer.quit()
        bank = SoundBank()
        bank.play("这个音效不存在")
        pygame.mixer.quit()

    def test_all_declared_effects_can_play(self):
        pygame.mixer.quit()
        bank = SoundBank()
        for effect in ("fly", "block", "clear", "all_clear", "fail", "click", "hint"):
            with self.subTest(effect=effect):
                bank.play(effect)
        pygame.mixer.quit()


class BonusUITestCase(TempSaveMixin, unittest.TestCase):
    """附加功能的界面行为。"""

    def setUp(self):
        super().setUp()
        self.app = ArrowPathApp(LEVELS, sound=False, save_path=self.save_path)

    def tearDown(self):
        pygame.quit()
        super().tearDown()

    def click(self, target):
        """target 可以是矩形，也可以是 (x, y) 坐标。"""
        point = target.center if hasattr(target, "center") else tuple(target)
        self.app.click(point)
        self.app.update(0.016)

    def button(self, action):
        for rect, _label, key in self.app.menu_buttons():
            if key == action:
                return rect
        raise AssertionError(f"菜单上没有 {action} 按钮")


class TestLevelSelect(BonusUITestCase):
    def test_menu_reaches_level_select(self):
        self.click(self.button("select"))
        self.assertIs(self.app.screen_state, Screen.LEVEL_SELECT)

    def test_level_select_lists_every_level(self):
        self.assertEqual(len(self.app.level_buttons()), len(LEVELS))

    def test_clicking_a_level_starts_it(self):
        self.app.goto_level_select()
        self.click(self.app.level_buttons()[3][0])
        self.assertIs(self.app.screen_state, Screen.PLAYING)
        self.assertEqual(self.app.game.level_index, 3)

    def test_back_button_returns_to_menu(self):
        self.app.goto_level_select()
        self.click(self.app.back_button_rect())
        self.assertIs(self.app.screen_state, Screen.MENU)

    def test_clicking_empty_area_in_level_select_does_nothing(self):
        self.app.goto_level_select()
        self.app.click((10, 10))
        self.assertIs(self.app.screen_state, Screen.LEVEL_SELECT)

    def test_every_level_can_be_started_and_drawn(self):
        for index in range(len(LEVELS)):
            with self.subTest(level=index):
                self.app.select_level(index)
                self.assertEqual(self.app.game.level_index, index)
                self.app.draw()


class TestHintButton(BonusUITestCase):
    def test_hint_highlights_a_clearable_arrow(self):
        self.app.start_game()
        arrow = self.app.use_hint()
        self.assertIsNotNone(arrow)
        self.assertIs(self.app.hint_arrow, arrow)
        self.assertTrue(self.app.game.board.is_path_clear(arrow))
        self.app.draw()

    def test_hint_expires_after_its_duration(self):
        self.app.start_game()
        self.app.use_hint()
        self.assertIsNotNone(self.app.hint_arrow)
        self.app.update(10.0)
        self.assertIsNone(self.app.hint_arrow, "提示应当自动消失")

    def test_hint_cleared_after_a_click(self):
        self.app.start_game()
        arrow = self.app.use_hint()
        self.app.click(self.app.cell_center(arrow.row, arrow.col))
        self.assertIsNone(self.app.hint_arrow)

    def test_hint_does_not_change_game_state(self):
        self.app.start_game()
        before = self.app.game.board.to_grid()
        mistakes = self.app.game.mistakes_left
        self.app.use_hint()
        self.assertEqual(self.app.game.board.to_grid(), before)
        self.assertEqual(self.app.game.mistakes_left, mistakes)


class TestUndoButton(BonusUITestCase):
    def test_undo_button_restores_previous_state(self):
        self.app.start_game()
        initial = self.app.game.board.to_grid()
        arrow = self.app.game.hint()
        self.click(self.app.cell_center(arrow.row, arrow.col))
        self.assertNotEqual(self.app.game.board.to_grid(), initial)

        self.assertTrue(self.app.undo())
        self.assertEqual(self.app.game.board.to_grid(), initial)

    def test_undo_does_nothing_without_history(self):
        self.app.start_game()
        self.assertFalse(self.app.undo())
        self.assertIs(self.app.screen_state, Screen.PLAYING)

    def test_undo_after_failure_returns_to_playing(self):
        self.app = ArrowPathApp([LEVELS[0]], sound=False, save_path=self.save_path)
        self.app.start_game()
        blocked = [
            a for a in self.app.game.board.arrows
            if not self.app.game.board.is_path_clear(a)
        ]
        for _ in range(self.app.game.max_mistakes):
            self.app.click(self.app.cell_center(blocked[0].row, blocked[0].col))
        self.assertIs(self.app.screen_state, Screen.FAILED)

        self.assertTrue(self.app.undo())
        self.assertIs(self.app.screen_state, Screen.PLAYING)


class TestAutoSolve(BonusUITestCase):
    def test_auto_solve_clears_the_level(self):
        self.app.start_game()
        self.assertTrue(self.app.toggle_auto_solve())

        for _ in range(500):
            self.app.update(0.05)
            self.app.draw()
            if self.app.screen_state is not Screen.PLAYING:
                break
        self.assertIs(
            self.app.screen_state, Screen.LEVEL_CLEARED, "自动求解应当能通关"
        )
        self.assertEqual(self.app.game.board.remaining, 0)

    def test_auto_solve_stops_on_toggle(self):
        self.app.start_game()
        self.app.toggle_auto_solve()
        self.app.update(1.0)
        self.assertFalse(self.app.toggle_auto_solve(), "再点一次应关闭")
        self.assertFalse(self.app.auto_solve)

    def test_auto_solve_solves_every_level(self):
        for index in range(len(LEVELS)):
            with self.subTest(level=index):
                self.app.select_level(index)
                self.app.toggle_auto_solve()
                for _ in range(800):
                    self.app.update(0.05)
                    if self.app.screen_state is not Screen.PLAYING:
                        break
                self.assertEqual(
                    self.app.game.board.remaining, 0, f"第 {index+1} 关没能自动解完"
                )


class TestScoreDisplay(BonusUITestCase):
    def test_clearing_awards_stars_and_score(self):
        self.app.start_game()
        for arrow in self.app.game.solve_order() or []:
            self.app.click(self.app.cell_center(arrow.row, arrow.col))
        self.assertIs(self.app.screen_state, Screen.LEVEL_CLEARED)
        self.assertEqual(self.app.game.stars(), 3, "零失误应当三星")
        self.assertGreater(self.app.game.total_score, 0)
        self.app.draw()

    def test_failure_shows_no_stars(self):
        self.app.start_game()
        blocked = [
            a for a in self.app.game.board.arrows
            if not self.app.game.board.is_path_clear(a)
        ]
        for _ in range(self.app.game.max_mistakes):
            self.app.click(self.app.cell_center(blocked[0].row, blocked[0].col))
        self.assertIs(self.app.screen_state, Screen.FAILED)
        self.app.draw()          # 失败面板不应画星

    def test_timer_advances_while_playing(self):
        self.app.start_game()
        for _ in range(20):
            self.app.update(0.1)
        self.assertGreater(self.app.game.elapsed, 0.5)

    def test_timer_stops_after_level_ends(self):
        self.app.start_game()
        for arrow in self.app.game.solve_order() or []:
            self.app.click(self.app.cell_center(arrow.row, arrow.col))
        frozen = self.app.game.elapsed
        for _ in range(20):
            self.app.update(0.1)
        self.assertAlmostEqual(self.app.game.elapsed, frozen, places=3)


class TestSaveViaUI(BonusUITestCase):
    def test_no_continue_button_without_a_save(self):
        self.assertIsNone(self.app.pending_save)
        self.assertNotIn("继续游戏", [label for _r, label, _a in self.app.menu_buttons()])

    def test_continue_button_appears_after_saving(self):
        self.app.start_game()
        self.assertTrue(self.app.save_progress())
        self.assertIsNotNone(self.app.pending_save)
        self.assertIn("继续游戏", [label for _r, label, _a in self.app.menu_buttons()])

    def test_continue_restores_progress(self):
        self.app.select_level(2)
        for arrow in (self.app.game.solve_order() or [])[:4]:
            self.app.click(self.app.cell_center(arrow.row, arrow.col))
        expected = self.app.game.board.to_grid()
        self.app.save_progress()

        fresh = ArrowPathApp(LEVELS, sound=False, save_path=self.save_path)
        try:
            self.assertIsNotNone(fresh.pending_save)
            rect = [r for r, _l, a in fresh.menu_buttons() if a == "continue"][0]
            fresh.click(rect.center)
            self.assertIs(fresh.screen_state, Screen.PLAYING)
            self.assertEqual(fresh.game.level_index, 2)
            self.assertEqual(fresh.game.board.to_grid(), expected)
        finally:
            pygame.quit()

    def test_clearing_a_level_saves_progress(self):
        self.app.start_game()
        for arrow in self.app.game.solve_order() or []:
            self.app.click(self.app.cell_center(arrow.row, arrow.col))
        self.assertTrue(
            self.save_path.exists(), "通关后应当自动存档"
        )

    def test_continue_without_save_is_a_noop(self):
        self.assertFalse(self.app.continue_game())
        self.assertIs(self.app.screen_state, Screen.MENU)


class TestKeyboardShortcuts(BonusUITestCase):
    def send_key(self, key):
        self.app.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": ""})
        )

    def test_h_uses_hint(self):
        self.app.start_game()
        self.send_key(pygame.K_h)
        self.assertIsNotNone(self.app.hint_arrow)

    def test_z_undoes(self):
        self.app.start_game()
        initial = self.app.game.board.remaining
        arrow = self.app.game.hint()
        self.app.click(self.app.cell_center(arrow.row, arrow.col))
        self.assertEqual(self.app.game.board.remaining, initial - 1)

        self.send_key(pygame.K_z)
        self.assertEqual(self.app.game.board.remaining, initial, "撤销后箭头数应复原")

    def test_a_toggles_auto_solve(self):
        self.app.start_game()
        self.send_key(pygame.K_a)
        self.assertTrue(self.app.auto_solve)

    def test_l_opens_level_select_and_back(self):
        self.send_key(pygame.K_l)
        self.assertIs(self.app.screen_state, Screen.LEVEL_SELECT)
        self.send_key(pygame.K_l)
        self.assertIs(self.app.screen_state, Screen.MENU)


if __name__ == "__main__":
    unittest.main(verbosity=2)
