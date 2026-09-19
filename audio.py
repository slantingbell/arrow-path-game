"""程序化音效（附加功能）。

所有音效都用代码合成，**不引入任何外部音频素材**，
因此项目依然满足"未使用第三方美术 / 音效素材"这一约束。

设备没有声卡、或运行在无头环境时，SoundBank 会自动降级为静音，
不影响游戏逻辑，也不影响自动化测试。
"""

from __future__ import annotations

import numpy as np
import pygame

SAMPLE_RATE = 44100


def _envelope(n: int, attack: float = 0.01, release: float = 0.6) -> np.ndarray:
    """简单的攻击 + 指数衰减包络，避免爆音。"""
    env = np.exp(-np.linspace(0.0, release * 6, n))
    attack_n = max(1, int(n * attack))
    env[:attack_n] *= np.linspace(0.0, 1.0, attack_n)
    return env


def _chirp(
    start_freq: float, end_freq: float, duration: float, volume: float = 0.35
) -> np.ndarray:
    """线性扫频。频率从 start_freq 滑到 end_freq。"""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0.0, duration, n, endpoint=False)
    k = (end_freq - start_freq) / duration
    phase = 2 * np.pi * (start_freq * t + 0.5 * k * t * t)
    return np.sin(phase) * _envelope(n) * volume


def _sequence(
    notes: list[tuple[float, float]], volume: float = 0.32, gap: float = 0.0
) -> np.ndarray:
    """把若干 (频率, 时长) 依次拼接成一小段旋律。"""
    parts = []
    for freq, duration in notes:
        n = int(SAMPLE_RATE * duration)
        t = np.linspace(0.0, duration, n, endpoint=False)
        tone = np.sin(2 * np.pi * freq * t) * _envelope(n, release=0.9)
        parts.append(tone * volume)
        if gap:
            parts.append(np.zeros(int(SAMPLE_RATE * gap)))
    return np.concatenate(parts)


def _to_sound(wave: np.ndarray) -> pygame.mixer.Sound:
    """把浮点波形转成 pygame Sound（单声道 16 位）。"""
    clipped = np.clip(wave, -1.0, 1.0)
    samples = (clipped * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(samples))


# 音效定义：名称 -> 生成函数
_SOUND_BUILDERS = {
    # 箭头飞出：上扬的短促扫频
    "fly": lambda: _chirp(520, 1180, 0.16, volume=0.30),
    # 碰撞：低沉的短音
    "block": lambda: _chirp(220, 90, 0.20, volume=0.35),
    # 本关通关：上行三音
    "clear": lambda: _sequence([(523.25, 0.11), (659.25, 0.11), (783.99, 0.20)]),
    # 全部通关：更长的上行乐句
    "all_clear": lambda: _sequence(
        [(523.25, 0.10), (659.25, 0.10), (783.99, 0.10), (1046.50, 0.30)]
    ),
    # 本关失败：下行两音
    "fail": lambda: _sequence([(392.00, 0.16), (261.63, 0.34)], volume=0.30),
    # 界面点击
    "click": lambda: _chirp(880, 660, 0.06, volume=0.18),
    # 提示
    "hint": lambda: _sequence([(880.0, 0.07), (1174.66, 0.12)], volume=0.20),
}


class SoundBank:
    """音效集合。初始化失败时自动静音，调用方无需关心。"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}

        if not enabled:
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1, buffer=512)
            if pygame.mixer.get_init()[2] != 1:
                # 实际拿到的是立体声，则把单声道波形复制成两列
                self._channels = pygame.mixer.get_init()[2]
            else:
                self._channels = 1

            for name, builder in _SOUND_BUILDERS.items():
                self._sounds[name] = self._make(builder)
            self.enabled = True
        except (pygame.error, ValueError, np.linalg.LinAlgError):
            # 没有可用音频设备，静音运行
            self.enabled = False
            self._sounds.clear()

    def _make(self, builder) -> pygame.mixer.Sound:
        wave = builder()
        if self._channels > 1:
            wave = np.repeat(wave.reshape(-1, 1), self._channels, axis=1)
        return _to_sound(wave)

    def play(self, name: str) -> None:
        """播放指定音效；不存在或已静音时什么也不做。"""
        if not self.enabled:
            return
        sound = self._sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass


if __name__ == "__main__":  # pragma: no cover - 手工试听
    pygame.init()
    bank = SoundBank()
    print("音效可用:", bank.enabled)
    for effect in _SOUND_BUILDERS:
        print("  播放", effect)
        bank.play(effect)
        pygame.time.wait(450)
    pygame.quit()
