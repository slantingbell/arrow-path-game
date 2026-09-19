# 测试记录（test.md）

本文档记录"一箭又一箭"小游戏的测试过程与结果，对应 PRD 第 8 节测试需求
（作业原文"三、任务要求 5. 测试要求"）。

---

## 1. 测试环境

| 项目 | 内容 |
| --- | --- |
| 操作系统 | Windows 11 Pro (10.0.26200) |
| Python | 3.14.5 |
| pygame-ce | 2.5.8 (SDL 2.32.10) |
| numpy | 2.4.6（音效合成用） |
| PyInstaller | 6.22.3（仅打包时用到） |
| 测试框架 | Python 标准库 `unittest`（无需额外安装） |
| 显示环境 | 无头运行（`SDL_VIDEODRIVER=dummy`） |

---

## 2. 运行方式

在项目根目录执行：

```bash
python -m unittest discover -s tests -t .
```

Windows 下如需在无显示设备的环境（例如远程终端）运行，可先设置无头驱动：

```bash
set SDL_VIDEODRIVER=dummy
```

打包出来的可执行文件另有自检入口，用于确认发布产物确实能跑：

```bash
./dist/一箭又一箭.exe --selftest report.txt
```

---

## 3. 测试方式说明

本次测试**全部为自动化测试**，共 177 个用例，分为三个文件：

| 文件 | 内容 | 用例数 |
| --- | --- | ---: |
| `tests/test_game.py` | 核心逻辑单元测试：方向、路径检测、边界、失误、状态流转、关卡校验、提示、撤销、计分、存档数据 | 63 |
| `tests/test_app.py` | 通过模拟鼠标点击驱动**真实界面**，覆盖作业要求的 T01–T06 | 64 |
| `tests/test_features.py` | 附加功能：关卡生成器、存档读写、音效、关卡选择、自动求解、打包自检 | 50 |

`tests/test_app.py` 并不直接调用 `game.Game`，而是构造真实的 `ArrowPathApp`，
把棋盘坐标换算成像素坐标后调用界面的点击处理入口，走完整链路：

```text
像素坐标 → cell_at() 换算 → click() 分发 → Game.click() 判定
        → 界面状态切换 → 登记飞出/碰撞动画
```

因此 T01–T06 既验证了游戏逻辑，也验证了界面交互与状态显示。

---

## 4. 作业要求测试 T01–T06

| 编号 | 测试内容 | 预期结果 | 实际结果 | 是否通过 |
| --- | --- | --- | --- | :---: |
| T01 | 点击前方无阻挡的箭头 | 箭头飞出棋盘并消失 | 点击后箭头从棋盘移除，剩余箭头数由 1 变 0，失误次数不变，并登记飞出动画 | ✅ |
| T02 | 点击前方有阻挡的箭头 | 箭头不消失，失误次数减 1 | 箭头仍在原格，剩余箭头数不变，失误次数由 3 变 2，并登记碰撞动画 | ✅ |
| T03 | 点击位于边缘且朝向棋盘外的箭头 | 箭头正常消失，不发生越界错误 | 边缘四个方向朝外的箭头均正常飞出，未出现 IndexError | ✅ |
| T04 | 消除本关全部箭头 | 显示通关并进入下一关 | 清空后显示通关界面；点击主按钮进入第 2 关，关卡号递增、布局与失误次数重置 | ✅ |
| T05 | 失误次数耗尽 | 显示失败并允许重新开始 | 失误归零后显示失败界面；点击主按钮可重新开始本关 | ✅ |
| T06 | 游戏进行中重新开始 | 箭头布局和失误次数恢复 | 点击"重新开始"按钮后，棋盘恢复初始布局，失误次数恢复为上限 | ✅ |

### 各测试项对应的具体用例

| 测试项 | 对应用例 |
| --- | --- |
| T01 | `TestT01ClearArrow::test_t01_arrow_flies_out_and_disappears`<br>`TestT01ClearArrow::test_t01_registers_fly_animation`<br>`TestT01ClearArrow::test_t01_animation_finishes_and_drains` |
| T02 | `TestT02BlockedArrow::test_t02_arrow_stays_and_mistake_decreases`<br>`TestT02BlockedArrow::test_t02_registers_shake_animation`<br>`TestT02BlockedArrow::test_t02_repeated_clicks_keep_decreasing` |
| T03 | `TestT03Boundary::test_t03_all_edge_outward_arrows_fly_out_without_index_error`<br>`TestT03Boundary::test_t03_every_cell_every_direction_click_is_safe`<br>`TestT03Boundary::test_t03_clearing_all_edge_arrows_clears_level` |
| T04 | `TestT04LevelCleared::test_t04_shows_cleared_then_advances`<br>`TestT04LevelCleared::test_t04_last_level_shows_all_cleared` |
| T05 | `TestT05MistakesExhausted::test_t05_shows_failure_when_mistakes_run_out`<br>`TestT05MistakesExhausted::test_t05_restart_after_failure`<br>`TestT05MistakesExhausted::test_t05_clicks_ignored_after_failure` |
| T06 | `TestT06Restart::test_t06_restart_button_restores_state`<br>`TestT06Restart::test_t06_restart_clears_animations`<br>`TestT06Restart::test_t06_restart_works_after_partial_progress` |

### T03 的强化验证

T03 针对的是"边缘越界"这一类典型错误（作业原文的 AIGC 示例中即提到
"向上判断时出现越界"）。除上述用例外，另加一个穷举测试：

- `test_every_edge_cell_every_direction_no_index_error`：在 4×5 棋盘上，
  对**每一个格子 × 每一个方向**都构造一个只含该箭头的棋盘并做路径检测，
  确认不会访问越界下标；
- `test_single_cell_board`：1×1 棋盘上四个方向均不越界。

---

## 5. 补充自动化测试

### 5.1 路径检测（对应 FR-04，占评分 25 分）

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_four_directions_clear_in_open_board` | 空旷棋盘上四个方向都能飞出 | ✅ |
| `test_four_directions_blocked_by_one_arrow` | 四个方向各放一个阻挡物，都判定为被阻挡 | ✅ |
| `test_assignment_example_one` | 作业原文示例 1：`R..U.` 中 R 右侧有箭头 → 不能飞出 | ✅ |
| `test_assignment_example_two` | 作业原文示例 2：`U...R` 中末尾 R 右侧无箭头 → 可以飞出 | ✅ |
| `test_gap_does_not_block` | 路径上只有空格不构成阻挡 | ✅ |
| `test_blocking_arrow_off_axis_is_ignored` | 不同行也不同列的箭头不构成阻挡 | ✅ |
| `test_blocked_then_clear_after_removal` | 移除阻挡物后，原本被挡的箭头变为可飞出 | ✅ |
| `test_foreign_arrow_rejected` | 传入不属于本棋盘的箭头时报错而非返回错误答案 | ✅ |

其中前两组直接取自作业原文给出的判定基准示例。

### 5.2 关卡（对应 LV-01 / LV-02）

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_at_least_three_levels` | 至少 3 个关卡 | ✅ |
| `test_all_shipped_levels_valid_and_solvable` | 全部关卡均**零失误可通关** | ✅ |
| `test_unsolvable_level_rejected` | 死锁关卡（`RL` 互相阻挡）会被拒绝 | ✅ |
| `test_level_without_arrows_rejected` | 没有箭头的关卡会被拒绝 | ✅ |
| `test_every_level_uses_all_four_directions` | 关卡整体覆盖上下左右四个方向 | ✅ |
| `test_levels_are_solvable_from_shipped_data` | 用真实关卡数据跑通"三关全部通关"的完整流程 | ✅ |

关卡可通关性是作业明确的扣分项（"关卡实际上无法通关"）。本项目在
`levels.py` 中提供 `validate_levels()`，用贪心求解器校验每一关，
启动时与测试中都会执行。

### 5.3 游戏流程与界面

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_click_empty_cell_changes_nothing` | 点击空格不改变任何状态 | ✅ |
| `test_click_after_level_ended_is_ignored` | 通关/失败后点击被忽略 | ✅ |
| `test_mistakes_never_go_negative` | 失误次数不会变成负数 | ✅ |
| `test_last_level_reports_all_cleared` | 最后一关通关进入"全部通关"状态 | ✅ |
| `test_cell_at_is_inverse_of_cell_center` | 像素坐标与格子坐标换算互为逆运算 | ✅ |
| `test_draw_does_not_crash_on_every_screen` | 五种界面状态均能正常渲染 | ✅ |
| `test_hud_reports_current_values` | 界面所需信息（关卡名、剩余箭头、剩余失误）均可取到 | ✅ |

### 5.4 界面切换不误触（`TestMenuButtonOnly` / `TestResultButtonsOnly`）

对应缺陷 3 的修复，确保只有点在按钮上才会切换界面：

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_start_button_enters_game` | 点"开始游戏"按钮进入游戏 | ✅ |
| `test_clicking_title_does_not_start` | 点标题不进入游戏 | ✅ |
| `test_clicking_rule_card_does_not_start` | 点规则说明卡片不进入游戏 | ✅ |
| `test_clicking_blank_areas_does_not_start` | 点四角空白处不进入游戏 | ✅ |
| `test_near_miss_clicks_just_outside_button_do_not_start` | 点在按钮外 2 像素处也不进入游戏 | ✅ |
| `test_result_screen_ignores_click_elsewhere` | 通关界面点其它位置不跳关 | ✅ |
| `test_failure_screen_ignores_click_elsewhere` | 失败界面点其它位置不重开 | ✅ |

### 5.5 窗口自由缩放（`TestResizeAndZoom`）

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_default_window_maps_identity` | 默认窗口下窗口坐标即画布坐标 | ✅ |
| `test_resize_scales_viewport` | 窗口放大到 2 倍时缩放比例同步为 2.0 | ✅ |
| `test_click_hits_right_cell_after_resize` | 放大 2 倍后点击仍命中正确格子 | ✅ |
| `test_click_hits_right_cell_after_shrink` | 缩小到 0.7 倍后点击仍命中正确格子 | ✅ |
| `test_window_to_logical_roundtrip` | 四种窗口尺寸下坐标换算可逆 | ✅ |
| `test_letterbox_keeps_aspect_ratio` | 窗口比例不符时保持等比并居中留白 | ✅ |
| `test_click_in_letterbox_is_ignored` | 点在留白上被忽略；按钮位置按偏移换算 | ✅ |
| `test_zoom_is_clamped` | 缩放系数被限制在 0.5–3.0 | ✅ |
| `test_zoom_changes_scale` | 滚轮 / 按键缩放确实改变呈现比例 | ✅ |
| `test_resize_enforces_minimum_size` | 窗口不会被缩到小于最小尺寸 | ✅ |
| `test_draw_after_resize_and_zoom_does_not_crash` | 三种尺寸 × 缩放组合下渲染正常 | ✅ |

---

### 5.6 鼠标悬停反馈（`TestHoverFeedback`）

鼠标移到箭头上时，箭头放大并亮起蓝色光晕，光标变为手型。

| 用例 | 验证内容 | 结果 |
| --- | --- | :---: |
| `test_hovering_an_arrow_marks_it` | 悬停在箭头上时正确标记该箭头 | ✅ |
| `test_hovering_an_empty_cell_clears_hover` | 悬停在空格上取消悬停 | ✅ |
| `test_hovering_outside_the_board_clears_hover` | 悬停在棋盘外取消悬停 | ✅ |
| `test_hover_does_not_change_game_state` | 悬停不改变盘面、失误数或界面状态 | ✅ |
| `test_hover_follows_the_removed_arrow` | 箭头被点掉后悬停目标同步失效 | ✅ |
| `test_hover_is_cleared_when_level_changes` | 重开 / 换关后清除悬停 | ✅ |
| `test_no_hover_outside_playing_screen` | 选关等非游戏界面不产生悬停 | ✅ |
| `test_hover_works_after_window_resize` | 窗口缩放后鼠标坐标换算正确、仍命中同一箭头 | ✅ |
| `test_hover_renders_differently_from_idle` | **像素级**：悬停格画面必须变化，其余格必须不变 | ✅ |
| `test_mouse_motion_event_updates_hover` | 鼠标移动事件即时更新悬停 | ✅ |
| `test_window_leave_clears_hover` | 鼠标移出窗口后清除悬停 | ✅ |
| `test_drawing_while_hovering_does_not_crash` | 逐格悬停并渲染均无异常 | ✅ |

其中 `test_hover_renders_differently_from_idle` 是把悬停前后的画面各渲染一遍、
按格子比较像素：既要求悬停格确实变化（防止"高亮没画出来"），也要求其余格不变
（防止"光晕糊到隔壁格子"）。纯状态断言测不出这类渲染问题。

### 5.7 附加功能（`tests/test_features.py` 等）

| 用例组 | 验证内容 | 结果 |
| --- | --- | :---: |
| `TestGenerator` | 多种尺寸 × 多种种子下生成的关卡**必定可通关**；同种子可复现、不同种子有差异；尺寸放不下时明确报错 | ✅ |
| `TestStorage` | 存档读写往返一致；文件缺失/损坏/版本不符一律返回 None；写入失败不抛异常 | ✅ |
| `TestAudio` | 音效可建立；关闭时播放是空操作；播放不存在的音效不报错 | ✅ |
| `TestLevelSelect` | 菜单可进入选关；列出全部关卡；点选跳关；返回；空白处点击无效果 | ✅ |
| `TestHintButton` | 提示指向的箭头确实可飞出；到时自动消失；点击后清除；不改变游戏状态 | ✅ |
| `TestUndoButton` | 撤销恢复盘面；无历史时不动作；失败后撤销可回到进行中 | ✅ |
| `TestAutoSolve` | 自动求解能通关**每一个**关卡 | ✅ |
| `TestScoreDisplay` | 零失误三星；失败不显示星；计时在结束后停止 | ✅ |
| `TestSaveViaUI` | 无存档不显示"继续游戏"；存档后出现；读档恢复到相同进度；通关自动存档 | ✅ |
| `TestKeyboardShortcuts` | H / Z / A / L 四个快捷键行为正确 | ✅ |
| `TestSelfTest` | 打包自检能跑通并写出报告，逐关报告已清空 | ✅ |

其中 `TestGenerator` 针对的是"关卡实际上无法通关"这一明确扣分项：
生成器采用逆序放置构造，可通关性由构造保证，测试再对生成结果复核一遍。

---

## 6. 测试过程中发现的缺陷

### 缺陷 1：pygame 重启后字体缓存失效导致崩溃

| 项目 | 内容 |
| --- | --- |
| 发现方式 | `test_draw_does_not_crash_on_every_screen` 在**连续多次运行**测试套件时偶发失败 |
| 现象 | `pygame.error: Invalid font (font module quit since font created)` |
| 原因 | `load_font()` 把 `pygame.font.Font` 缓存在模块级字典中，而 `pygame.quit()` 会让这些 Font 对象全部失效；缓存仍然继续返回失效对象，于是再次初始化后绘制文字时抛出异常 |
| 复现 | 创建应用 → `pygame.quit()` → 再次创建应用并绘制，第二次绘制必崩 |
| 修复 | `load_font()` 先检查 `pygame.font.get_init()`，必要时重新初始化并清空缓存；`ArrowPathApp.__init__()` 在 `pygame.init()` 之后也会清空缓存 |
| 回归测试 | `test_font_cache_survives_pygame_restart`、`test_load_font_returns_usable_font_after_quit` |
| 状态 | ✅ 已修复并验证 |

该缺陷只在**反复退出再初始化**时出现，正常玩游戏不会触发；但只要有"重启游戏"
或"连续运行测试"的场景就会崩溃，因此属于真实缺陷而非测试问题。

### 缺陷 2：测试用例自身的错误期望（非产品缺陷）

首次运行时有 3 个用例失败，复核后确认是**测试写错了**，程序行为正确：

| 用例 | 错误之处 | 处理 |
| --- | --- | --- |
| `test_blocked_consumes_one_mistake` | 关卡 `["RU..","...D","..L."]` 实际有 4 个箭头，用例误写为 3 | 修正期望值为 4 |
| `test_restart_restores_board_and_mistakes` | 同上，移除 1 个后应为 3 个，用例误写为 2 | 修正期望值为 3 |
| `test_gap_does_not_block` | 用例用 `["R...U"]`，同行的 `U` 确实构成阻挡，与用例名称矛盾 | 改用 `["R...."]` 表达"只有空格不阻挡" |
| `test_click_in_letterbox_is_ignored` | 用例用 `view.x + rect.centerx` 当作"留白处"，但这其实是按钮**正确**的位置，点击后应当进入游戏 | 改为点击未换算的坐标 `rect.center`，并补上换算后能命中按钮的断言 |

### 缺陷 3：开始界面点击任意位置都会进入第一关

| 项目 | 内容 |
| --- | --- |
| 现象 | 在开始界面点击标题、规则文字或任意空白处，都会直接进入第 1 关，只有点"开始游戏"按钮才进入的预期不成立 |
| 原因 | `ArrowPathApp.click()` 在 `Screen.MENU` 分支里无条件调用 `start_game()`，完全没有判断点击位置是否落在按钮上 |
| 影响 | 玩家（或评审者）想看看规则说明，随手一点就进了游戏，属于明显的交互缺陷 |
| 修复 | 菜单分支改为仅当 `menu_button_rect().collidepoint(pos)` 时才调用 `start_game()`；同时把通关 / 失败 / 全部通关三个界面也一并改为**只响应主按钮**的点击，避免同类误触 |
| 回归测试 | `TestMenuButtonOnly`（5 个用例）、`TestResultButtonsOnly`（2 个用例），包含"点在按钮外 2 像素处不触发"的边界用例 |
| 状态 | ✅ 已修复并验证 |

### 新增能力：窗口自由缩放

| 项目 | 内容 |
| --- | --- |
| 需求 | 游戏界面可以自由缩放 |
| 实现 | 所有绘制改到一块固定尺寸的**逻辑画布**（720×830）上，再整体等比缩放呈现到窗口 |
| 关键点 | 窗口被缩放后，鼠标位置必须换算回画布坐标（`window_to_logical()`），否则点击会与画面错位 |
| 留白处理 | 窗口比例与画布不一致时保持等比并在居中位置留白，留白上的点击被忽略 |
| 缩放方式 | 拖拽窗口边缘；鼠标滚轮；`+` / `-` 键；`0` 键复位。缩放系数限制在 0.5–3.0 |
| 回归测试 | `TestResizeAndZoom`（11 个用例） |
| 状态 | ✅ 已实现并验证 |

### 缺陷 4：7×7 棋盘放不下画布，导致该关永远清不完

| 项目 | 内容 |
| --- | --- |
| 发现方式 | 新增第 6 关（7×7）后，`test_levels_are_solvable_from_shipped_data` 失败 |
| 现象 | 该关怎么点都清不空，界面状态一直停在 PLAYING |
| 原因 | 格子边长固定 96，7×7 棋盘高度为 `7×96 + 6×8 = 720`，加上顶部 208 后达到 928，超出 830 的逻辑画布。超出部分的格子坐标仍然合法，但点击会在 `window_to_logical()` 的越界判断处被丢弃，表现为"点了没反应" |
| 修复 | 格子边长改为按行列数自适应（`cell_size()`），上限 96、下限 28，保证棋盘一定完整落在画布内。4×4/5×5 仍是 96，6×6 降为 81，7×7 降为 68 |
| 回归测试 | `test_all_shipped_boards_fit_in_canvas`（逐格断言不越界）、`test_larger_boards_use_smaller_cells` |
| 状态 | ✅ 已修复并验证 |

### 缺陷 5：撤销按钮"可用"与"不可用"外观完全相同

| 项目 | 内容 |
| --- | --- |
| 发现方式 | 人工查看 `02-playing.png` 截图 |
| 现象 | 已经走过好几步、撤销明明可用，但按钮看起来和灰掉的禁用状态一模一样 |
| 原因 | 绘制时无论可用与否都传了 `COLOR_MUTED` 作为填充色，`disabled` 参数只在填充色相同时才生效，等于没区分 |
| 修复 | 可用时改用描边样式（白底蓝框），不可用时才用灰底 |
| 回归测试 | 由 `TestLayout` 一组的整体布局断言覆盖 |
| 状态 | ✅ 已修复并验证 |

### 缺陷 6：结果面板的得分文字压在按钮上

| 项目 | 内容 |
| --- | --- |
| 发现方式 | 人工查看 `03-level-cleared.png` 截图 |
| 现象 | "本关得分 986 · 累计 986"这行字与"进入下一关"按钮重叠 |
| 原因 | 文字画在 `panel.top + 130`，字号 19 时约占 111–149；按钮却从 `panel.top + 136` 开始 |
| 修复 | 面板高度由 232 增至 262，按钮下移到 `panel.top + 172`，两者留出明显间距 |
| 回归测试 | `test_result_panel_fits_and_button_clears_detail_text` |
| 状态 | ✅ 已修复并验证 |

### 缺陷 7：打包后存档写进临时目录，退出即丢失

| 项目 | 内容 |
| --- | --- |
| 发现方式 | 准备打包时审查代码，`storage.SAVE_PATH` 用的是 `Path(__file__).parent` |
| 现象 | PyInstaller 的 `--onefile` 会把代码解包到临时目录再运行，`__file__` 指向那里；存档写进去会随进程退出一起消失，表现为"存档功能在 exe 里不好使" |
| 影响 | 只在打包产物中出现，源码运行完全正常，属于典型的"只有发布后才暴露"的问题 |
| 修复 | 新增 `storage._default_save_path()`：检测到 `sys.frozen` 时把存档放到可执行文件同目录 |
| 回归测试 | 由 `--selftest` 在打包产物上实际运行验证 |
| 状态 | ✅ 已修复并验证 |

---

## 7. 测试有效性验证（变异测试）

"测试全部通过"本身不能说明测试有效——如果用例断言过弱，即使程序有 Bug 也会通过。
为确认测试确实能发现问题，人为注入三个典型缺陷，检查测试套件是否会失败：

| 注入的缺陷 | 说明 | 失败的用例数 | 结论 |
| --- | --- | ---: | --- |
| 忽略阻挡，永远返回"可飞出" | 完全不做路径检测 | 20 | ✅ 被捕获 |
| 只看紧邻一格 | 只检查箭头前方一格是否有阻挡 | 3 | ✅ 被捕获 |
| 边缘朝外误判为被阻挡 | 典型的越界处理错误 | 58 | ✅ 被捕获 |
| 菜单点击任意处即开始 | 还原缺陷 3 的旧行为 | 15 | ✅ 被捕获 |
| 缩放后不做坐标换算 | 窗口坐标直接当画布坐标用 | 7 | ✅ 被捕获 |
| 结果界面点击任意处即继续 | 结果界面不加按钮判断 | 4 | ✅ 被捕获 |

针对附加功能又补了四个：

| 注入的缺陷 | 说明 | 失败的用例数 | 结论 |
| --- | --- | ---: | --- |
| 提示随便指第一个箭头 | 不检查路径是否真的通畅 | 3 | ✅ 被捕获 |
| 撤销不恢复失误次数 | 只还原盘面、漏掉失误计数 | 2 | ✅ 被捕获 |
| 存档不做篡改校验 | 任意棋盘都照单全收 | 2 | ✅ 被捕获 |
| 生成器不做逆序放置 | 改成随机撒点，可通关性失去保证 | 35 | ✅ 被捕获 |

针对鼠标悬停反馈又补了三个：

| 注入的缺陷 | 说明 | 失败的用例数 | 结论 |
| --- | --- | ---: | --- |
| 完全不处理悬停 | `update_hover()` 直接返回 None | 9 | ✅ 被捕获 |
| 悬停不产生画面变化 | 状态照常记录，但绘制时忽略 hovered | 1 | ✅ 被捕获（像素级用例） |
| 切关后不清悬停 | `_reset_effects()` 漏清 hover | 1 | ✅ 被捕获 |

十三个变异全部被测试套件捕获，说明用例具备实际的检错能力。

其中"悬停不产生画面变化"只有像素级用例能抓到——它验证的正是"状态对了但没画出来"
这类问题，普通断言在这种情况下会全部通过。

> 补充：第一次跑这组变异时脚本**卡死了**。原因是"按提示点完能清空棋盘"那个用例
> 写的是 `while game.board.remaining:`，而变异后的提示会指向被挡住的箭头——
> 失误耗尽后点击被忽略，`remaining` 永远不降，循环无限空转。
> 已在用例中加上循环上限与终局断言。这也说明变异测试除了验证用例有效性，
> 还能暴露用例自身的健壮性问题。

---

## 8. 测试结果汇总

```text
Ran 177 tests in 13.2s

OK
```

| 项目 | 结果 |
| --- | --- |
| 用例总数 | 177 |
| 通过 | 177 |
| 失败 | 0 |
| 错误 | 0 |
| 作业要求测试 T01–T06 | 6 / 6 全部通过 |
| 发现的产品缺陷 | 6（均已修复并加回归测试） |

---

## 9. 未覆盖的部分

以下内容无法用自动化测试覆盖，由人工确认：

| 项目 | 说明 |
| --- | --- |
| 动画观感 | 飞出位移与碰撞晃动的视觉效果是否自然，需人工试玩判断 |
| 中文字体显示 | 测试只验证"能渲染不报错"；实际字形是否正确需人工查看 |
| 布局美观度 | 界面排版是否合理清晰，属主观判断 |
| 关卡难度体验 | 六个关卡的实际游玩难度与趣味性，需人工试玩 |
| 通关顺序合理性 | 已用求解器验证"存在通关顺序"，但顺序是否够巧妙仍需人工试玩 |
| 音效听感 | 只验证了音效可以生成、可以播放，具体音色是否悦耳需人工试听 |
| 实际窗口交互 | 窗口拖拽缩放的流畅度、滚轮缩放的步长手感，需人工操作确认 |
| 打包产物的图形界面 | exe 已用 `--selftest` 验证逻辑与渲染，但真实窗口显示需人工运行确认 |
