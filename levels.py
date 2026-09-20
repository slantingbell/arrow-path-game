"""关卡数据。

棋盘用字符串列表书写：
    'U' / 'D' / 'L' / 'R' = 该方向的箭头
    '.'                   = 空格

每个关卡都必须**零失误可通关**（作业要求："每个关卡都应由本人实际试玩，
确保存在合理的通关顺序"）。levels.py 末尾的 validate_levels() 会用
game.greedy_clearable() 对全部关卡做一次机器校验，main.py 启动时与
自动化测试都会调用它，防止把关卡改成不可通关的死锁。
"""

from __future__ import annotations


LEVELS: list[dict] = [
    {
        "name": "第 1 关 · 入门",
        "max_mistakes": 3,
        # 四个角向外，中央两个箭头互相牵制，用来理解"前方有箭头则不能飞出"。
        "grid": [
            "U..D",
            "...L",
            "R...",
            "U..D",
        ],
    },
    {
        "name": "第 2 关 · 顺序",
        "max_mistakes": 3,
        # 必须先清掉四角的箭头，中央的 U / R 才有出路。
        "grid": [
            "U...D",
            ".U.L.",
            ".....",
            ".U.R.",
            "U...D",
        ],
    },
    {
        "name": "第 3 关 · 对称",
        "max_mistakes": 4,
        # 左右镜像的 5x5 布局，12 个箭头中有 10 个初始被阻挡。
        # 必须从底部两角的 D 开始，逐层向外解锁。
        "grid": [
            "DL.RD",
            ".....",
            ".U.U.",
            ".U.U.",
            "DL.RD",
        ],
    },
    # 以下三关由 generator.py 以固定随机种子生成（同一个种子必定得到同一布局），
    # 采用"逆序放置"构造，可通关性由构造保证，再经 validate_levels() 复核。
    {
        "name": "第 4 关 · 交错",
        "max_mistakes": 4,
        "generated": True,
        "grid": [
            "..L..D",
            ".L.L.D",
            "..R.DD",
            ".U...R",
            "U..RD.",
            "....R.",
        ],
    },
    {
        "name": "第 5 关 · 密林",
        "max_mistakes": 4,
        "generated": True,
        "grid": [
            "..R...",
            ".U..U.",
            "L.UR.R",
            ".L..LU",
            "LLL.R.",
            "...R.U",
        ],
    },
    {
        "name": "第 6 关 · 终局",
        "max_mistakes": 5,
        "generated": True,
        "grid": [
            "L.RRR..",
            "...UUR.",
            "L.U.R.R",
            ".......",
            "D....R.",
            "....RRR",
            "L..L...",
        ],
    },
]


def validate_levels(levels: list[dict] | None = None) -> None:
    """校验全部关卡：棋盘合法，且都能在零失误下通关。

    关卡不可通关会抛出 ValueError —— 这是作业明确的扣分项，
    宁可在启动时立刻失败，也不要让玩家玩到一半发现是死局。
    """
    # 延迟导入：levels.py 与 game.py 互相独立，避免循环导入问题。
    from game import Board, greedy_clearable

    for index, level in enumerate(levels if levels is not None else LEVELS):
        grid = level["grid"]
        if level["max_mistakes"] < 1:
            raise ValueError(f"关卡 {index} 的失误次数必须至少为 1")

        board = Board.from_grid(grid)  # 同时校验字符合法与行长一致
        if board.remaining == 0:
            raise ValueError(f"关卡 {index} 没有任何箭头")
        if not greedy_clearable(board):
            raise ValueError(
                f"关卡 {index}（{level.get('name', '')}）无法通关："
                f"剩余箭头互相阻挡形成死锁 {board.to_grid()}"
            )


if __name__ == "__main__":  # pragma: no cover - 手工校验入口
    from game import Board

    validate_levels()
    for i, lv in enumerate(LEVELS, 1):
        b = Board.from_grid(lv["grid"])
        blocked = sum(1 for a in b.arrows if not b.is_path_clear(a))
        print(
            f"{lv['name']}: {b.rows}x{b.cols}, 箭头 {b.remaining} 个, "
            f"初始被阻挡 {blocked} 个, 失误上限 {lv['max_mistakes']} —— 可通关 ✓"
        )
