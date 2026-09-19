"""一箭又一箭 (Arrow Path Game) —— 核心游戏逻辑。

本模块不导入任何图形库，因此可以在没有显示设备的环境中直接测试。
图形界面见 main.py。

棋盘表示为一个 R 行 × C 列的二维网格，每个格子要么是 None（空格），
要么是一个 Arrow(row, col, direction)。箭头不会移动，只会被消除，
因此"某箭头前方是否被阻挡"只取决于同一行/列上是否还有其他箭头。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# 方向 → 单字符符号，用于在关卡数据里书写棋盘。
_DIRECTION_SYMBOLS = {
    "UP": "U",
    "DOWN": "D",
    "LEFT": "L",
    "RIGHT": "R",
}


class Direction(Enum):
    """箭头的四个方向。value 为 (行增量, 列增量)。"""

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def delta(self) -> tuple[int, int]:
        """返回该方向的行、列增量。"""
        return self.value

    @property
    def symbol(self) -> str:
        """返回该方向在关卡数据中的单字符符号，如 'U'。"""
        return _DIRECTION_SYMBOLS[self.name]


SYMBOL_TO_DIRECTION = {v: Direction[k] for k, v in _DIRECTION_SYMBOLS.items()}

EMPTY_CELL = "."


class GameStatus(Enum):
    """一局游戏（当前关卡）的状态。"""

    PLAYING = "playing"          # 游戏进行中
    CLEARED = "cleared"          # 本关通过，还有下一关
    ALL_CLEARED = "all_cleared"  # 最后一关通过，全部通关
    FAILED = "failed"            # 失误次数耗尽，本关失败


class ClickKind(Enum):
    """一次点击的结果类型。"""

    FLY_OUT = "fly_out"  # 前方无阻挡，箭头飞出棋盘
    BLOCKED = "blocked"  # 前方有阻挡，箭头不消失，失误次数 -1
    EMPTY = "empty"      # 点在空格上，无任何效果
    IGNORED = "ignored"  # 本关已结束（通关或失败），点击被忽略


@dataclass(frozen=True)
class Arrow:
    """棋盘上的一个箭头。"""

    row: int
    col: int
    direction: Direction

    @property
    def symbol(self) -> str:
        return self.direction.symbol

    def __str__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"{self.symbol}({self.row},{self.col})"


@dataclass(frozen=True)
class ClickOutcome:
    """一次点击的完整结果，供界面层决定播放哪种反馈动画。"""

    kind: ClickKind
    arrow: Arrow | None
    mistakes_left: int
    status: GameStatus

    @property
    def level_ended(self) -> bool:
        return self.status in (GameStatus.CLEARED, GameStatus.ALL_CLEARED, GameStatus.FAILED)


class Board:
    """游戏棋盘：一组带方向的箭头 + 路径检测。"""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self._grid: list[list[Arrow | None]] = [[None] * cols for _ in range(rows)]

    @classmethod
    def from_grid(cls, grid: list[str]) -> "Board":
        """从字符串列表构造棋盘。

        每个字符串是一行，字符含义：
            'U' / 'D' / 'L' / 'R' = 该方向箭头
            '.'                   = 空格

        所有行必须等长，否则抛出 ValueError。
        """
        if not grid:
            raise ValueError("关卡棋盘不能为空")

        cols = len(grid[0])
        for index, line in enumerate(grid):
            if len(line) != cols:
                raise ValueError(
                    f"第 {index} 行长度为 {len(line)}，与第 0 行的 {cols} 不一致"
                )

        board = cls(len(grid), cols)
        for r, line in enumerate(grid):
            for c, char in enumerate(line):
                if char == EMPTY_CELL:
                    continue
                if char not in SYMBOL_TO_DIRECTION:
                    raise ValueError(
                        f"第 {r} 行第 {c} 列出现非法字符 {char!r}，"
                        f"只允许 {EMPTY_CELL} 或 U/D/L/R"
                    )
                board._grid[r][c] = Arrow(r, c, SYMBOL_TO_DIRECTION[char])
        return board

    # ---- 查询 ----

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def arrow_at(self, row: int, col: int) -> Arrow | None:
        """返回该格子的箭头，空格或越界返回 None。"""
        if not self.in_bounds(row, col):
            return None
        return self._grid[row][col]

    @property
    def arrows(self) -> list[Arrow]:
        return [a for row in self._grid for a in row if a is not None]

    @property
    def remaining(self) -> int:
        """棋盘上剩余箭头数量。"""
        return sum(1 for row in self._grid for a in row if a is not None)

    def is_path_clear(self, arrow: Arrow) -> bool:
        """判断 arrow 沿其朝向到棋盘边界之间是否没有其他箭头。

        从箭头前一个格子开始沿方向逐格前进，直到走出棋盘：
        途中遇到任何箭头即视为被阻挡。

        箭头位于边缘且朝向棋盘外时，扫描区间为空，直接判定为可飞出，
        不会访问越界下标（对应测试 T03）。

        若传入的箭头不属于本棋盘，直接抛出 ValueError —— 否则会基于
        另一个棋盘的布局给出看似合理却错误的结果。
        """
        if self.arrow_at(arrow.row, arrow.col) is not arrow:
            raise ValueError(f"箭头 {arrow} 不属于当前棋盘")
        dr, dc = arrow.direction.delta
        r, c = arrow.row + dr, arrow.col + dc
        while self.in_bounds(r, c):
            if self._grid[r][c] is not None:
                return False
            r += dr
            c += dc
        return True

    # ---- 修改 ----

    def remove(self, arrow: Arrow) -> None:
        """把箭头从棋盘上移除。"""
        if self._grid[arrow.row][arrow.col] is not arrow:
            raise ValueError(f"棋盘上不存在箭头 {arrow}")
        self._grid[arrow.row][arrow.col] = None

    def clear_arrows(self) -> None:
        """移除所有箭头。"""
        self._grid = [[None] * self.cols for _ in range(self.rows)]

    def to_grid(self) -> list[str]:
        """导出为字符串网格，便于调试与关卡校验。"""
        return [
            "".join(a.symbol if a is not None else EMPTY_CELL for a in row)
            for row in self._grid
        ]

    def copy(self) -> "Board":
        """返回一个内容相同的独立棋盘（箭头为不可变对象，可安全共享）。"""
        clone = Board(self.rows, self.cols)
        clone._grid = [row[:] for row in self._grid]
        return clone


def greedy_clearable(board: Board) -> bool:
    """判断棋盘能否在"零失误"前提下被清空。

    由于箭头只会被移除、不会移动，移除一个箭头只会让其它箭头的路径
    变得更通畅，绝不会反过来造成新的阻挡（单调性）。因此"反复移除所有
    当前可飞出的箭头"这一贪心策略是完备的：若存在零失误解法，贪心一定
    能找到；若贪心卡住而棋盘非空，则说明剩下箭头互相阻挡成了死锁。

    关卡设计时用它来保证"每个关卡都实际可通关"。
    """
    work = board.copy()
    while work.remaining:
        clearable = [a for a in work.arrows if work.is_path_clear(a)]
        if not clearable:
            return False
        for arrow in clearable:
            work.remove(arrow)
    return True


class Game:
    """一局游戏：管理当前关卡、失误次数与关卡流转。"""

    def __init__(self, levels: list[dict], level_index: int = 0) -> None:
        if not levels:
            raise ValueError("至少需要一个关卡")
        self.levels = list(levels)
        self.level_index = level_index
        self.board: Board
        self.max_mistakes: int
        self.mistakes_left: int
        self.status: GameStatus
        self.restart()

    # ---- 关卡信息 ----

    @property
    def level_number(self) -> int:
        """当前关卡序号，从 1 开始。"""
        return self.level_index + 1

    @property
    def total_levels(self) -> int:
        return len(self.levels)

    @property
    def is_last_level(self) -> bool:
        return self.level_index == self.total_levels - 1

    @property
    def level_name(self) -> str:
        return self.levels[self.level_index].get("name") or f"第 {self.level_number} 关"

    # ---- 操作 ----

    def restart(self) -> None:
        """把当前关卡恢复到初始状态（箭头布局与失误次数）。"""
        level = self.levels[self.level_index]
        self.board = Board.from_grid(level["grid"])
        self.max_mistakes = level["max_mistakes"]
        self.mistakes_left = self.max_mistakes
        self.status = GameStatus.PLAYING

    def click(self, row: int, col: int) -> ClickOutcome:
        """点击一个格子，返回本次点击的结果。

        本关已结束时点击一律忽略（不改变任何状态）。
        """
        if self.status is not GameStatus.PLAYING:
            return ClickOutcome(ClickKind.IGNORED, None, self.mistakes_left, self.status)

        arrow = self.board.arrow_at(row, col)
        if arrow is None:
            return ClickOutcome(ClickKind.EMPTY, None, self.mistakes_left, self.status)

        if self.board.is_path_clear(arrow):
            self.board.remove(arrow)
            if self.board.remaining == 0:
                self.status = (
                    GameStatus.ALL_CLEARED if self.is_last_level else GameStatus.CLEARED
                )
            return ClickOutcome(ClickKind.FLY_OUT, arrow, self.mistakes_left, self.status)

        self.mistakes_left = max(0, self.mistakes_left - 1)
        if self.mistakes_left == 0:
            self.status = GameStatus.FAILED
        return ClickOutcome(ClickKind.BLOCKED, arrow, self.mistakes_left, self.status)

    def next_level(self) -> bool:
        """进入下一关。已是最后一关时返回 False。"""
        if self.is_last_level:
            return False
        self.level_index += 1
        self.restart()
        return True

    def solve_order(self) -> list[Arrow] | None:
        """返回一个零失误通关顺序；若无法通关则返回 None。

        使用与 greedy_clearable 相同的贪心策略，供提示 / 自动求解功能使用。
        """
        work = self.board.copy()
        order: list[Arrow] = []
        while work.remaining:
            clearable = [a for a in work.arrows if work.is_path_clear(a)]
            if not clearable:
                return None
            arrow = clearable[0]
            order.append(arrow)
            work.remove(arrow)
        return order
