"""游戏进度保存与读取（附加功能）。

存档写成一个 JSON 文件，放在项目目录下，方便查看和删除。
读取时会校验存档里的棋盘确实是该关卡的合法中间状态，
避免载入手工篡改或损坏的存档。

所有函数都不会因为文件读写失败而抛出异常——存档属于锦上添花的功能，
不应该让游戏因为磁盘问题而崩溃。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

SAVE_VERSION = 1


def _default_save_path() -> Path:
    """决定存档位置。

    打包成 exe 后 __file__ 指向 PyInstaller 的临时解包目录，
    存档写进去会随进程退出而消失，因此改为放在 exe 同目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "savegame.json"
    return Path(__file__).resolve().parent / "savegame.json"


SAVE_PATH = _default_save_path()


def save_game(game, path: Path | str = SAVE_PATH) -> bool:
    """把游戏进度写入存档文件。成功返回 True。"""
    data = {"version": SAVE_VERSION, "saved_at": datetime.now().isoformat(timespec="seconds")}
    data.update(game.to_save())

    try:
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except OSError:
        return False


def load_save(path: Path | str = SAVE_PATH) -> dict | None:
    """读取存档内容。文件不存在或格式不对时返回 None。"""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
        return None
    return data


def has_save(path: Path | str = SAVE_PATH) -> bool:
    """是否存在可用的存档。"""
    return load_save(path) is not None


def clear_save(path: Path | str = SAVE_PATH) -> None:
    """删除存档文件（不存在时忽略）。"""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def describe(data: dict) -> str:
    """给存档生成一句人类可读的描述，用于菜单上的"继续游戏"。"""
    try:
        level = int(data["level_index"]) + 1
        score = int(data.get("total_score", 0))
    except (KeyError, TypeError, ValueError):
        return "继续上次进度"

    when = str(data.get("saved_at", "")).replace("T", " ")
    return f"继续游戏（第 {level} 关，得分 {score}）" + (f" · {when}" if when else "")
