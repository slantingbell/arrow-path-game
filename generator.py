"""随机生成"保证可通关"的关卡（附加功能）。

关键思路是**逆序放置**，而不是"先生成再筛选"：

    放置第 k 个箭头时，要求它沿自身方向的路径上不含任何已放置的箭头。

于是把这些箭头按放置的**逆序**移除时，第 k 个箭头在轮到它时，
棋盘上只剩下在它之前放置的那些箭头，而它们都不在它的路径上，
所以它必定可以飞出。可解性由构造本身保证，不需要事后用求解器筛。

这样生成出来的关卡天然满足"至少存在一个零失误通关顺序"，
不可能出现死锁布局。
"""

from __future__ import annotations

import random

from game import Board, Direction

# 每关失误上限：随箭头数量略微放宽
MISTAKES_BY_SIZE = ((6, 3), (9, 3), (12, 4))


def _build_once(
    rows: int, cols: int, n_arrows: int, rng: random.Random
) -> tuple[list[str], int]:
    """按逆序放置构造一个棋盘，返回 (网格, 实际放置数量)。"""
    grid = [["."] * cols for _ in range(rows)]
    placed = 0

    for _ in range(n_arrows):
        empties = [
            (r, c) for r in range(rows) for c in range(cols) if grid[r][c] == "."
        ]
        rng.shuffle(empties)

        for r, c in empties:
            directions = list(Direction)
            rng.shuffle(directions)
            for direction in directions:
                dr, dc = direction.delta
                rr, cc = r + dr, c + dc
                clear = True
                while 0 <= rr < rows and 0 <= cc < cols:
                    if grid[rr][cc] != ".":
                        clear = False
                        break
                    rr += dr
                    cc += dc
                if clear:
                    grid[r][c] = direction.symbol
                    placed += 1
                    break
            else:
                continue
            break

    return ["".join(row) for row in grid], placed


def generate_grid(
    rows: int,
    cols: int,
    n_arrows: int,
    rng: random.Random | None = None,
    attempts: int = 60,
) -> list[str]:
    """生成一个刚好包含 n_arrows 个箭头、且保证可通关的棋盘。

    在若干次构造中挑"初始被阻挡的箭头最多"的那一个，让关卡更有解谜感
    （箭头全都朝外就太简单了）。
    """
    rng = rng or random.Random()

    best_grid: list[str] | None = None
    best_blocked = -1

    for _ in range(attempts):
        grid, placed = _build_once(rows, cols, n_arrows, rng)
        if placed != n_arrows:
            continue

        board = Board.from_grid(grid)
        blocked = sum(1 for a in board.arrows if not board.is_path_clear(a))
        if blocked > best_blocked:
            best_blocked = blocked
            best_grid = grid
        if blocked == n_arrows:  # 已经不可能更好
            break

    if best_grid is None:
        raise ValueError(
            f"{rows}x{cols} 的棋盘放不下 {n_arrows} 个满足条件的箭头"
        )
    return best_grid


def max_mistakes_for(n_arrows: int) -> int:
    """按箭头数量给出失误上限。"""
    for threshold, mistakes in MISTAKES_BY_SIZE:
        if n_arrows <= threshold:
            return mistakes
    return 5


def generate_level(
    rows: int,
    cols: int,
    n_arrows: int,
    seed: int | None = None,
    name: str | None = None,
) -> dict:
    """生成一个可直接放进 LEVELS 的关卡字典。"""
    rng = random.Random(seed)
    grid = generate_grid(rows, cols, n_arrows, rng)
    return {
        "name": name or f"随机 {rows}x{cols}",
        "grid": grid,
        "max_mistakes": max_mistakes_for(n_arrows),
        "generated": True,
    }


def random_level(seed: int | None = None, difficulty: int = 1) -> dict:
    """按难度生成一个随机关卡，难度越高棋盘越大、箭头越多。

    difficulty 从 1 开始，越大越难。
    """
    preset = {
        1: (4, 4, 6),
        2: (5, 5, 9),
        3: (5, 5, 12),
        4: (6, 6, 15),
        5: (6, 6, 18),
    }
    rows, cols, n_arrows = preset.get(max(1, min(5, difficulty)), (5, 5, 12))
    return generate_level(rows, cols, n_arrows, seed=seed)


if __name__ == "__main__":  # pragma: no cover - 手工查看生成效果
    from game import greedy_clearable

    for difficulty in range(1, 6):
        level = random_level(seed=difficulty * 7, difficulty=difficulty)
        board = Board.from_grid(level["grid"])
        blocked = sum(1 for a in board.arrows if not board.is_path_clear(a))
        print(f"难度 {difficulty}: 箭头 {board.remaining}, 初始被阻挡 {blocked}, "
              f"可通关 {greedy_clearable(board)}")
        for line in level["grid"]:
            print("   ", line)
