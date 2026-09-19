"""核心逻辑单元测试：方向、路径检测、边界、失误与状态流转。

这些测试只依赖 game.py，不需要图形环境。
运行：python -m unittest discover -s tests -t .
"""

from __future__ import annotations

import unittest

from game import (
    Board,
    ClickKind,
    Direction,
    Game,
    GameStatus,
    greedy_clearable,
)
from levels import LEVELS, validate_levels


def make_game(grid, max_mistakes=3):
    return Game([{"name": "测试关", "grid": grid, "max_mistakes": max_mistakes}])


class TestBoardConstruction(unittest.TestCase):
    def test_grid_roundtrip(self):
        grid = ["R..U", ".D.L"]
        self.assertEqual(Board.from_grid(grid).to_grid(), grid)

    def test_empty_cells_have_no_arrow(self):
        board = Board.from_grid([".R.", "..."])
        self.assertIsNone(board.arrow_at(0, 0))
        self.assertIsNone(board.arrow_at(1, 1))
        self.assertIsNotNone(board.arrow_at(0, 1))

    def test_remaining_counts_arrows(self):
        self.assertEqual(Board.from_grid(["UDLR", "...."]).remaining, 4)

    def test_ragged_rows_rejected(self):
        with self.assertRaises(ValueError):
            Board.from_grid(["R..", ".."])

    def test_illegal_character_rejected(self):
        with self.assertRaises(ValueError):
            Board.from_grid(["RX."])

    def test_arrow_at_out_of_bounds_is_none(self):
        board = Board.from_grid(["R."])
        self.assertIsNone(board.arrow_at(-1, 0))
        self.assertIsNone(board.arrow_at(0, 5))
        self.assertIsNone(board.arrow_at(9, 9))


class TestDirections(unittest.TestCase):
    def test_all_four_symbols_parse(self):
        board = Board.from_grid(["UDLR"])
        expected = [
            Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT,
        ]
        self.assertEqual([a.direction for a in board.arrows], expected)

    def test_direction_deltas(self):
        self.assertEqual(Direction.UP.delta, (-1, 0))
        self.assertEqual(Direction.DOWN.delta, (1, 0))
        self.assertEqual(Direction.LEFT.delta, (0, -1))
        self.assertEqual(Direction.RIGHT.delta, (0, 1))


class TestPathDetection(unittest.TestCase):
    """FR-04：正确判断箭头前进方向上是否存在其他箭头。"""

    def test_four_directions_clear_in_open_board(self):
        """四个方向在空旷棋盘上都能飞出。"""
        for symbol in "UDLR":
            with self.subTest(direction=symbol):
                board = Board.from_grid(["...", f".{symbol}.", "..."])
                arrow = board.arrow_at(1, 1)
                self.assertTrue(
                    board.is_path_clear(arrow), f"{symbol} 前方无阻挡应可飞出"
                )

    def test_four_directions_blocked_by_one_arrow(self):
        """中心箭头朝四个方向，各自紧邻一个阻挡箭头，都应判定为被阻挡。"""
        # (中心箭头方向, 阻挡物相对中心的偏移)
        cases = {
            "UP": ("U", (-1, 0)),
            "DOWN": ("D", (1, 0)),
            "LEFT": ("L", (0, -1)),
            "RIGHT": ("R", (0, 1)),
        }
        for name, (center_dir, (dr, dc)) in cases.items():
            with self.subTest(direction=name):
                grid = [["."] * 5 for _ in range(5)]
                grid[2][2] = center_dir
                grid[2 + dr][2 + dc] = "U"  # 阻挡物方向无关，只看是否占格
                board = Board.from_grid(["".join(r) for r in grid])
                self.assertFalse(
                    board.is_path_clear(board.arrow_at(2, 2)),
                    f"{name} 方向有阻挡应判定为不可飞出",
                )

    def test_blocked_then_clear_after_removal(self):
        """移除阻挡物后，原本被挡的箭头变为可飞出。"""
        board = Board.from_grid(["RU."])
        target = board.arrow_at(0, 0)
        self.assertFalse(board.is_path_clear(target))
        board.remove(board.arrow_at(0, 1))
        self.assertTrue(board.is_path_clear(target))

    def test_assignment_example_one(self):
        """作业原文示例 1：第一个箭头朝右，但右侧仍有其他箭头，因此不能飞出。"""
        board = Board.from_grid(["R..U."])
        self.assertFalse(board.is_path_clear(board.arrow_at(0, 0)))

    def test_assignment_example_two(self):
        """作业原文示例 2：最后一个箭头朝右，右侧没有其他箭头，因此可以飞出。"""
        board = Board.from_grid(["U...R"])
        self.assertTrue(board.is_path_clear(board.arrow_at(0, 4)))

    def test_gap_does_not_block(self):
        """路径上只有空格不构成阻挡。"""
        board = Board.from_grid(["R...."])
        self.assertTrue(board.is_path_clear(board.arrow_at(0, 0)))

    def test_blocking_arrow_off_axis_is_ignored(self):
        """不同行也不同列的箭头不构成阻挡。"""
        board = Board.from_grid(["R..", "...", "..U"])
        self.assertTrue(board.is_path_clear(board.arrow_at(0, 0)))

    def test_foreign_arrow_rejected(self):
        """传入不属于本棋盘的箭头应报错，而不是给出错误答案。"""
        board_a = Board.from_grid(["R.."])
        board_b = Board.from_grid(["..R"])
        with self.assertRaises(ValueError):
            board_a.is_path_clear(board_b.arrow_at(0, 2))


class TestBoundary(unittest.TestCase):
    """T03：边缘箭头朝棋盘外，不应发生越界错误。"""

    def test_corner_arrows_pointing_outward(self):
        board = Board.from_grid(["U.U", "L.R", "D.D"])
        for arrow in board.arrows:
            with self.subTest(arrow=str(arrow)):
                self.assertTrue(board.is_path_clear(arrow))

    def test_every_edge_cell_every_direction_no_index_error(self):
        """棋盘每个格子、每个方向都检测一遍，确认不会越界。"""
        rows, cols = 4, 5
        for r in range(rows):
            for c in range(cols):
                for d in "UDLR":
                    with self.subTest(cell=(r, c), direction=d):
                        grid = [["."] * cols for _ in range(rows)]
                        grid[r][c] = d
                        board = Board.from_grid(["".join(x) for x in grid])
                        arrow = board.arrow_at(r, c)
                        # 空旷棋盘上任何方向都应可飞出，且不抛异常
                        self.assertTrue(board.is_path_clear(arrow))

    def test_single_cell_board(self):
        for d in "UDLR":
            with self.subTest(direction=d):
                board = Board.from_grid([d])
                self.assertTrue(board.is_path_clear(board.arrow_at(0, 0)))


class TestGameFlow(unittest.TestCase):
    def test_click_empty_cell_changes_nothing(self):
        game = make_game(["R..", "..."])
        before = game.board.to_grid()
        outcome = game.click(1, 1)
        self.assertIs(outcome.kind, ClickKind.EMPTY)
        self.assertEqual(game.board.to_grid(), before)
        self.assertEqual(game.mistakes_left, game.max_mistakes)

    def test_fly_out_removes_arrow(self):
        game = make_game(["U..", "...", "..D"])
        outcome = game.click(0, 0)
        self.assertIs(outcome.kind, ClickKind.FLY_OUT)
        self.assertEqual(game.board.remaining, 1)

    def test_blocked_consumes_one_mistake(self):
        game = make_game(["RU..", "...D", "..L."], max_mistakes=3)
        self.assertEqual(game.board.remaining, 4)
        outcome = game.click(0, 0)  # R 被同行的 U 挡住
        self.assertIs(outcome.kind, ClickKind.BLOCKED)
        self.assertEqual(game.mistakes_left, 2)
        self.assertEqual(game.board.remaining, 4, "被阻挡的箭头不应消失")

    def test_click_after_level_ended_is_ignored(self):
        game = make_game(["U..", "...", "..D"])
        game.click(0, 0)   # 只清掉一个，仍剩一个
        self.assertIs(game.status, GameStatus.PLAYING)
        game.click(2, 2)   # 清空
        self.assertIs(game.status, GameStatus.ALL_CLEARED)
        outcome = game.click(0, 0)
        self.assertIs(outcome.kind, ClickKind.IGNORED)

    def test_restart_restores_board_and_mistakes(self):
        game = make_game(["RU..", "...D", "..L."], max_mistakes=3)
        initial = game.board.to_grid()
        game.click(0, 0)          # 失误一次（R 被 U 挡住）
        game.click(1, 3)          # 移除一个箭头
        self.assertEqual(game.mistakes_left, 2)
        self.assertEqual(game.board.remaining, 3)

        game.restart()
        self.assertEqual(game.board.to_grid(), initial)
        self.assertEqual(game.mistakes_left, 3)
        self.assertIs(game.status, GameStatus.PLAYING)

    def test_mistakes_never_go_negative(self):
        game = make_game(["RU..", "...D", "..L."], max_mistakes=2)
        game.click(0, 0)
        game.click(0, 0)
        self.assertEqual(game.mistakes_left, 0)
        self.assertIs(game.status, GameStatus.FAILED)

    def test_last_level_reports_all_cleared(self):
        game = Game([
            {"name": "one", "grid": ["U.."], "max_mistakes": 3},
            {"name": "two", "grid": ["..R"], "max_mistakes": 3},
        ])
        game.click(0, 0)
        self.assertIs(game.status, GameStatus.CLEARED, "还有下一关时应为 CLEARED")

        self.assertTrue(game.next_level())
        self.assertEqual(game.level_number, 2)
        game.click(0, 2)
        self.assertIs(game.status, GameStatus.ALL_CLEARED)

    def test_next_level_returns_false_at_end(self):
        game = make_game(["U.."])
        self.assertFalse(game.next_level())

    def test_empty_level_list_rejected(self):
        with self.assertRaises(ValueError):
            Game([])


class TestSolver(unittest.TestCase):
    def test_deadlock_detected(self):
        """R 与 L 互相阻挡，无法零失误通关。"""
        self.assertFalse(greedy_clearable(Board.from_grid(["RL"])))

    def test_chain_is_solvable(self):
        """必须先清右侧的 R，左侧的 R 才有出路。"""
        self.assertTrue(greedy_clearable(Board.from_grid(["RR"])))

    def test_solve_order_clears_board(self):
        game = make_game(["RR"])
        order = game.solve_order()
        self.assertIsNotNone(order)
        for arrow in order:
            outcome = game.click(arrow.row, arrow.col)
            self.assertIs(outcome.kind, ClickKind.FLY_OUT)
        self.assertEqual(game.board.remaining, 0)


class TestLevelData(unittest.TestCase):
    """LV-01 / LV-02：至少 3 关，且每关都实际可通关。"""

    def test_at_least_three_levels(self):
        self.assertGreaterEqual(len(LEVELS), 3)

    def test_all_shipped_levels_valid_and_solvable(self):
        validate_levels()  # 不可通关会抛 ValueError

    def test_every_level_has_positive_mistakes(self):
        for level in LEVELS:
            with self.subTest(level=level["name"]):
                self.assertGreaterEqual(level["max_mistakes"], 1)

    def test_unsolvable_level_rejected(self):
        with self.assertRaises(ValueError):
            validate_levels([{"name": "死锁", "grid": ["RL"], "max_mistakes": 3}])

    def test_level_without_arrows_rejected(self):
        with self.assertRaises(ValueError):
            validate_levels([{"name": "空", "grid": ["..."], "max_mistakes": 3}])

    def test_every_level_uses_all_four_directions(self):
        """FR-02：棋盘中包含上、下、左、右四种方向的箭头（整体覆盖）。"""
        used = set()
        for level in LEVELS:
            for arrow in Board.from_grid(level["grid"]).arrows:
                used.add(arrow.direction.symbol)
        self.assertEqual(used, {"U", "D", "L", "R"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
