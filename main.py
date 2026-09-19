"""一箭又一箭 (Arrow Path Game) —— pygame 图形界面与程序入口。

运行：
    python main.py

本模块把"界面状态"与"游戏逻辑"分开：所有规则判定都在 game.Game 里完成，
这里只负责把状态画出来，并把鼠标点击翻译成 Game.click() 调用。
点击处理与坐标换算都是普通方法，因此测试可以在无显示设备的环境下
（SDL_VIDEODRIVER=dummy）直接驱动界面，见 tests/test_app.py。
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from enum import Enum

import pygame

from game import Arrow, ClickKind, Direction, Game, GameStatus
from levels import LEVELS, validate_levels

# ---------------------------------------------------------------- 布局常量

# 逻辑画布尺寸。所有绘制都按这个尺寸进行，再整体缩放到实际窗口，
# 因此窗口可以自由拉伸，界面布局不会被拉坏。
LOGICAL_W, LOGICAL_H = 720, 830
CELL = 96          # 单个格子边长
GAP = 8            # 格子间距
BOARD_TOP = 208    # 棋盘上边缘
FPS = 60

INITIAL_SIZE = (LOGICAL_W, LOGICAL_H)   # 启动时的窗口大小
MIN_SIZE = (360, 415)                   # 窗口最小尺寸
MIN_ZOOM, MAX_ZOOM = 0.5, 3.0           # 手动缩放范围
ZOOM_STEP = 0.1                         # 每格滚轮的缩放步长
COLOR_LETTERBOX = (232, 234, 238)       # 窗口留白（保持比例时的补边）

# 配色
COLOR_BG = (248, 249, 251)
COLOR_BOARD = (255, 255, 255)
COLOR_GRID = (223, 226, 232)
COLOR_ARROW = (64, 112, 214)
COLOR_ARROW_BLOCK = (222, 74, 74)
COLOR_TEXT = (33, 38, 48)
COLOR_MUTED = (120, 128, 140)
COLOR_BTN = (64, 112, 214)
COLOR_BTN_TEXT = (255, 255, 255)
COLOR_OK = (39, 160, 96)
COLOR_FAIL = (210, 60, 60)

# 动画时长（秒）
FLY_DURATION = 0.28
SHAKE_DURATION = 0.32


class Screen(Enum):
    """界面状态。"""

    MENU = "menu"                    # 开始界面
    PLAYING = "playing"              # 游戏界面
    LEVEL_CLEARED = "level_cleared"  # 本关通关
    FAILED = "failed"                # 本关失败
    ALL_CLEARED = "all_cleared"      # 全部关卡通关


# ---------------------------------------------------------------- 字体

_CJK_FONT_PATHS = (
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
)

_CJK_SYSFONT_NAMES = (
    "microsoftyaheui", "microsoftyahei", "simhei", "simsun",
    "notosanscjksc", "notosanscjk", "pingfangsc", "wenquanyizenhei",
)

_font_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def clear_font_cache() -> None:
    """丢弃已缓存的字体。

    pygame.quit() 会让此前创建的 Font 对象全部失效，但缓存里仍然留着它们，
    再次初始化后取出来就会抛 "Invalid font (font module quit since font created)"。
    因此在重新 init 之后必须清空缓存。
    """
    _font_cache.clear()


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """加载一个支持中文的字体，按平台依次回退。

    找不到任何中文字体时退回 pygame 默认字体（中文会显示为方块），
    但不影响程序运行，也不影响自动化测试。
    """
    if not pygame.font.get_init():
        # 字体模块被 quit 过，缓存里的 Font 已失效，必须重建。
        pygame.font.init()
        clear_font_cache()

    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]

    font: pygame.font.Font | None = None
    for path in _CJK_FONT_PATHS:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                break
            except OSError:
                continue

    if font is None:
        for name in _CJK_SYSFONT_NAMES:
            match = pygame.font.match_font(name, bold=bold)
            if match:
                font = pygame.font.Font(match, size)
                break

    if font is None:
        font = pygame.font.Font(None, size)

    if bold:
        font.set_bold(True)
    _font_cache[key] = font
    return font


# ---------------------------------------------------------------- 动画


@dataclass
class FlyAnimation:
    """箭头飞出棋盘的动画。逻辑上箭头已被移除，这里只画一个残影。"""

    arrow: Arrow
    progress: float = 0.0

    @property
    def finished(self) -> bool:
        return self.progress >= 1.0

    def offset(self, cell: int) -> tuple[float, float]:
        """按飞出距离计算位移：走到足够远，视觉上离开棋盘。"""
        dr, dc = self.arrow.direction.delta
        travel = (self.arrow.row + self.arrow.col + 2) * (cell + GAP)
        eased = 1 - (1 - self.progress) ** 2  # 缓出
        return dc * travel * eased, dr * travel * eased


@dataclass
class ShakeAnimation:
    """箭头被阻挡时的晃动 + 变红反馈。"""

    arrow: Arrow
    progress: float = 0.0

    @property
    def finished(self) -> bool:
        return self.progress >= 1.0

    @property
    def offset_x(self) -> float:
        """左右晃动，振幅随进度衰减；结束时归零。"""
        if self.progress >= 1.0:
            return 0.0
        decay = 1.0 - self.progress
        return 12 * decay * math.cos(self.progress * 8 * math.pi)


# ---------------------------------------------------------------- 应用


class ArrowPathApp:
    """游戏应用：持有界面状态、动画队列与点击分发。"""

    def __init__(
        self,
        levels: list[dict] | None = None,
        size: tuple[int, int] = INITIAL_SIZE,
    ) -> None:
        validate_levels(levels if levels is not None else LEVELS)

        pygame.init()
        # pygame.quit() 后再次 init，字体模块是全新的，旧缓存必须丢弃。
        clear_font_cache()
        pygame.display.set_caption("一箭又一箭 | 拖拽窗口边缘或滚轮缩放")
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        # 所有绘制都画在这块固定尺寸的画布上，最后整体缩放到窗口。
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        self.zoom = 1.0
        self.clock = pygame.time.Clock()

        self.levels = list(levels if levels is not None else LEVELS)
        self.game = Game(self.levels)
        self.screen_state = Screen.MENU
        self.running = False

        self.fly_anims: list[FlyAnimation] = []
        self.shake_anims: list[ShakeAnimation] = []

    # -------------------------------------------------- 缩放与坐标换算

    def viewport(self) -> tuple[pygame.Rect, float]:
        """返回 (画布在窗口中的位置, 缩放比例)。

        先按窗口大小等比缩放"适应窗口"（letterbox），再乘以手动缩放系数。
        缩放系数大于适应比例时画面会超出窗口，居中显示并裁掉四周。
        """
        win_w, win_h = self.window.get_size()
        fit = min(win_w / LOGICAL_W, win_h / LOGICAL_H)
        scale = fit * self.zoom
        w, h = max(1, round(LOGICAL_W * scale)), max(1, round(LOGICAL_H * scale))
        return pygame.Rect((win_w - w) // 2, (win_h - h) // 2, w, h), scale

    def window_to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        """把窗口坐标换算成画布（逻辑）坐标。

        窗口被缩放或拉伸后，鼠标位置必须换算回画布坐标，
        否则点击位置会和画面错位。
        """
        view, scale = self.viewport()
        if scale <= 0:
            return pos
        return (
            (pos[0] - view.x) / scale,
            (pos[1] - view.y) / scale,
        )

    def set_zoom(self, zoom: float) -> None:
        """设置手动缩放系数（在"适应窗口"的基础上再缩放）。"""
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, round(zoom, 3)))

    def zoom_by(self, delta: float) -> None:
        self.set_zoom(self.zoom + delta)

    def resize(self, size: tuple[int, int]) -> None:
        """调整窗口大小，并保证不小于最小尺寸。"""
        w = max(MIN_SIZE[0], size[0])
        h = max(MIN_SIZE[1], size[1])
        self.window = pygame.display.set_mode((w, h), pygame.RESIZABLE)

    def present(self) -> None:
        """把画布缩放后呈现到窗口。"""
        view, _ = self.viewport()
        self.window.fill(COLOR_LETTERBOX)
        if view.width == LOGICAL_W and view.height == LOGICAL_H:
            self.window.blit(self.canvas, view.topleft)
        else:
            self.window.blit(pygame.transform.smoothscale(self.canvas, view.size), view.topleft)
        pygame.display.flip()

    # -------------------------------------------------- 几何换算

    def board_origin(self) -> tuple[int, int]:
        """棋盘左上角像素坐标（按棋盘尺寸水平居中）。"""
        board_w = self.game.board.cols * CELL + (self.game.board.cols - 1) * GAP
        return (LOGICAL_W - board_w) // 2, BOARD_TOP

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        """第 row 行第 col 列格子的矩形。"""
        ox, oy = self.board_origin()
        return pygame.Rect(
            ox + col * (CELL + GAP),
            oy + row * (CELL + GAP),
            CELL,
            CELL,
        )

    def cell_center(self, row: int, col: int) -> tuple[int, int]:
        return self.cell_rect(row, col).center

    def cell_at(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """把像素坐标换算成 (row, col)；不在任何格子上则返回 None。"""
        for row in range(self.game.board.rows):
            for col in range(self.game.board.cols):
                if self.cell_rect(row, col).collidepoint(pos):
                    return row, col
        return None

    # -------------------------------------------------- 按钮

    def restart_button_rect(self) -> pygame.Rect:
        return pygame.Rect(LOGICAL_W - 168, 34, 136, 46)

    def primary_button_rect(self) -> pygame.Rect:
        """结果界面（通关 / 失败 / 全部通关）的主按钮，位于结果面板内。"""
        panel = self.result_panel_rect()
        return pygame.Rect(panel.centerx - 110, panel.top + 136, 220, 58)

    def menu_button_rect(self) -> pygame.Rect:
        """开始界面上的"开始游戏"按钮。"""
        return pygame.Rect(LOGICAL_W // 2 - 110, 470, 220, 60)

    # -------------------------------------------------- 点击处理

    def click(self, pos: tuple[int, int]) -> ClickKind | None:
        """处理一次左键点击，pos 为**窗口坐标**。

        界面层不重复实现任何规则判定，一律委托给 Game。
        所有界面切换都必须点在对应按钮上，点其它地方不会误触发。
        """
        x, y = self.window_to_logical(pos)
        if not (0 <= x < LOGICAL_W and 0 <= y < LOGICAL_H):
            return None  # 点在保持比例产生的留白上

        logical = (x, y)

        if self.screen_state is Screen.MENU:
            # 只有点到"开始游戏"按钮才进入游戏
            if self.menu_button_rect().collidepoint(logical):
                self.start_game()
            return None

        if self.screen_state is Screen.PLAYING:
            if self.restart_button_rect().collidepoint(logical):
                self.restart_level()
                return None
            cell = self.cell_at(logical)
            if cell is None:
                return None
            return self.click_cell(*cell)

        # 通关 / 失败 / 全部通关：只有点到主按钮才继续
        if not self.primary_button_rect().collidepoint(logical):
            return None

        if self.screen_state is Screen.LEVEL_CLEARED:
            self.advance_level()
        elif self.screen_state is Screen.FAILED:
            self.restart_level()
        elif self.screen_state is Screen.ALL_CLEARED:
            self.back_to_menu()

        return None

    def click_cell(self, row: int, col: int) -> ClickKind:
        """点击棋盘上的一个格子，并按结果登记反馈动画。"""
        outcome = self.game.click(row, col)

        if outcome.kind is ClickKind.FLY_OUT and outcome.arrow is not None:
            self.fly_anims.append(FlyAnimation(outcome.arrow))
        elif outcome.kind is ClickKind.BLOCKED and outcome.arrow is not None:
            self.shake_anims.append(ShakeAnimation(outcome.arrow))

        if outcome.status is GameStatus.CLEARED:
            self.screen_state = Screen.LEVEL_CLEARED
        elif outcome.status is GameStatus.ALL_CLEARED:
            self.screen_state = Screen.ALL_CLEARED
        elif outcome.status is GameStatus.FAILED:
            self.screen_state = Screen.FAILED

        return outcome.kind

    # -------------------------------------------------- 状态切换

    def start_game(self) -> None:
        self.game.level_index = 0
        self.game.restart()
        self._reset_effects()
        self.screen_state = Screen.PLAYING

    def restart_level(self) -> None:
        """把当前关卡恢复到初始状态（箭头布局与失误次数）。"""
        self.game.restart()
        self._reset_effects()
        self.screen_state = Screen.PLAYING

    def advance_level(self) -> None:
        if self.game.next_level():
            self._reset_effects()
            self.screen_state = Screen.PLAYING
        else:
            self.screen_state = Screen.ALL_CLEARED

    def back_to_menu(self) -> None:
        self._reset_effects()
        self.screen_state = Screen.MENU

    def _reset_effects(self) -> None:
        self.fly_anims.clear()
        self.shake_anims.clear()

    # -------------------------------------------------- 更新

    def update(self, dt: float) -> None:
        for anim in self.fly_anims:
            anim.progress = min(1.0, anim.progress + dt / FLY_DURATION)
        self.fly_anims = [a for a in self.fly_anims if not a.finished]

        for anim in self.shake_anims:
            anim.progress = min(1.0, anim.progress + dt / SHAKE_DURATION)
        self.shake_anims = [a for a in self.shake_anims if not a.finished]

    @property
    def busy(self) -> bool:
        """是否还有动画在播放。"""
        return bool(self.fly_anims or self.shake_anims)

    # -------------------------------------------------- 绘制

    def draw_canvas(self) -> None:
        """把当前界面画到逻辑画布上（不呈现到窗口）。"""
        self.canvas.fill(COLOR_BG)
        if self.screen_state is Screen.MENU:
            self._draw_menu()
        else:
            self._draw_hud()
            self._draw_board()
            self._draw_footer_prompt()

    def draw(self) -> None:
        """绘制并呈现到窗口。"""
        self.draw_canvas()
        self.present()

    def result_panel_rect(self) -> pygame.Rect:
        """结果提示面板：浮在棋盘中央，避免与不同大小的棋盘打架。"""
        return pygame.Rect(LOGICAL_W // 2 - 250, 372, 500, 232)

    def _draw_text(
        self,
        text: str,
        size: int,
        pos: tuple[int, int],
        color: tuple[int, int, int] = COLOR_TEXT,
        bold: bool = False,
        center: bool = False,
    ) -> pygame.Rect:
        font = load_font(size, bold)
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        self.canvas.blit(surface, rect)
        return rect

    def _draw_button(self, rect: pygame.Rect, label: str, color=COLOR_BTN) -> None:
        pygame.draw.rect(self.canvas, color, rect, border_radius=10)
        self._draw_text(label, 24, rect.center, COLOR_BTN_TEXT, bold=True, center=True)

    def _draw_menu(self) -> None:
        self._draw_text("一箭又一箭", 72, (LOGICAL_W // 2, 150), COLOR_TEXT, bold=True, center=True)
        self._draw_text(
            "点击箭头，让它沿自己的方向飞出棋盘", 25,
            (LOGICAL_W // 2, 228), COLOR_MUTED, center=True,
        )

        # 规则说明卡片
        card = pygame.Rect(LOGICAL_W // 2 - 270, 286, 540, 132)
        pygame.draw.rect(self.canvas, COLOR_BOARD, card, border_radius=14)
        self._draw_text(
            "前方没有其他箭头阻挡时才能飞出", 21,
            (LOGICAL_W // 2, 322), COLOR_TEXT, center=True,
        )
        self._draw_text(
            "被挡住则无法消除，并消耗一次失误机会", 21,
            (LOGICAL_W // 2, 356), COLOR_MUTED, center=True,
        )
        self._draw_text(
            "失误次数耗尽即本关失败", 21,
            (LOGICAL_W // 2, 390), COLOR_MUTED, center=True,
        )

        self._draw_button(self.menu_button_rect(), "开始游戏")
        self._draw_text(
            f"共 {len(self.levels)} 关", 20,
            (LOGICAL_W // 2, 572), COLOR_MUTED, center=True,
        )

    def _draw_hud(self) -> None:
        """顶部信息栏：当前关卡、剩余箭头、剩余失误、重新开始按钮。"""
        self._draw_text(self.game.level_name, 30, (36, 34), COLOR_TEXT, bold=True)

        arrows_left = self.game.board.remaining
        self._draw_text(f"剩余箭头 {arrows_left}", 22, (36, 84), COLOR_MUTED)
        self._draw_text(
            f"当前关卡 {self.game.level_number} / {self.game.total_levels}",
            20, (36, 118), COLOR_MUTED,
        )

        mistakes = self.game.mistakes_left
        color = COLOR_FAIL if mistakes <= 1 else COLOR_TEXT
        self._draw_text(
            f"剩余失误 {mistakes} / {self.game.max_mistakes}",
            22, (LOGICAL_W - 36 - 200, 84), color,
        )

        self._draw_button(self.restart_button_rect(), "重新开始", COLOR_MUTED)

    def _draw_board(self) -> None:
        board = self.game.board
        origin_x, origin_y = self.board_origin()
        width = board.cols * CELL + (board.cols - 1) * GAP
        height = board.rows * CELL + (board.rows - 1) * GAP

        pygame.draw.rect(
            self.canvas, COLOR_BOARD,
            pygame.Rect(origin_x - 12, origin_y - 12, width + 24, height + 24),
            border_radius=14,
        )

        for row in range(board.rows):
            for col in range(board.cols):
                pygame.draw.rect(
                    self.canvas, COLOR_GRID, self.cell_rect(row, col), border_radius=10
                )

        # 被阻挡的箭头仍在棋盘上，叠加晃动与变红反馈。
        shaking = {id(a.arrow): a for a in self.shake_anims}
        for arrow in board.arrows:
            shake = shaking.get(id(arrow))
            self._draw_arrow(arrow, shake.offset_x if shake else 0.0, bool(shake))

        # 已飞出的箭头逻辑上已移除，这里只画飞出残影。
        for anim in self.fly_anims:
            self._draw_arrow(anim.arrow, 0.0, False, fly=anim)

    def _draw_arrow(
        self,
        arrow: Arrow,
        offset_x: float = 0.0,
        collided: bool = False,
        fly: FlyAnimation | None = None,
    ) -> None:
        rect = self.cell_rect(arrow.row, arrow.col)
        center = pygame.math.Vector2(rect.center) + pygame.math.Vector2(offset_x, 0)

        if fly is not None:
            dx, dy = fly.offset(CELL)
            center += pygame.math.Vector2(dx, dy)

        half = CELL // 2 - 26
        cx, cy = center
        d = arrow.direction

        if d is Direction.UP:
            points = [(cx, cy - half), (cx - half, cy + half), (cx + half, cy + half)]
        elif d is Direction.DOWN:
            points = [(cx, cy + half), (cx - half, cy - half), (cx + half, cy - half)]
        elif d is Direction.LEFT:
            points = [(cx - half, cy), (cx + half, cy - half), (cx + half, cy + half)]
        else:
            points = [(cx + half, cy), (cx - half, cy - half), (cx - half, cy + half)]

        color = COLOR_ARROW_BLOCK if collided else COLOR_ARROW
        pygame.draw.polygon(self.canvas, color, points)
        pygame.draw.polygon(self.canvas, COLOR_BOARD, points, width=2)

    def _draw_footer_prompt(self) -> None:
        """游戏中的提示文字，以及通关 / 失败时的结果面板。"""
        if self.screen_state is Screen.PLAYING:
            self._draw_text(
                "点击箭头让它飞出棋盘", 20,
                (LOGICAL_W // 2, LOGICAL_H - 40), COLOR_MUTED, center=True,
            )
            return

        if self.screen_state is Screen.LEVEL_CLEARED:
            self._draw_result_panel(
                f"{self.game.level_name} 通关！", "进入下一关", COLOR_OK
            )
        elif self.screen_state is Screen.FAILED:
            self._draw_result_panel(
                "失误次数已用完，本关失败", "重新开始本关", COLOR_FAIL
            )
        elif self.screen_state is Screen.ALL_CLEARED:
            self._draw_result_panel("恭喜！全部关卡通关", "回到主菜单", COLOR_OK)

    def _draw_result_panel(self, title: str, button_label: str, color) -> None:
        """在棋盘中央浮出一个半透明结果面板。"""
        panel = self.result_panel_rect()

        backdrop = pygame.Surface(panel.size, pygame.SRCALPHA)
        backdrop.fill((255, 255, 255, 242))
        self.canvas.blit(backdrop, panel.topleft)
        pygame.draw.rect(self.canvas, color, panel, width=3, border_radius=18)

        self._draw_text(
            title, 30, (panel.centerx, panel.top + 60), color, bold=True, center=True
        )
        self._draw_button(self.primary_button_rect(), button_label, color)

    # -------------------------------------------------- 主循环

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.VIDEORESIZE:
            self.window = pygame.display.set_mode(
                (max(MIN_SIZE[0], event.w), max(MIN_SIZE[1], event.h)),
                pygame.RESIZABLE,
            )

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            elif event.key == pygame.K_r and self.screen_state is Screen.PLAYING:
                self.restart_level()
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.zoom_by(ZOOM_STEP)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.zoom_by(-ZOOM_STEP)
            elif event.key == pygame.K_0:
                self.set_zoom(1.0)      # 恢复到适应窗口

        elif event.type == pygame.MOUSEWHEEL:
            self.zoom_by(ZOOM_STEP * event.y)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)

    def run(self) -> None:
        self.running = True
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
        pygame.quit()


def main() -> int:
    app = ArrowPathApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
