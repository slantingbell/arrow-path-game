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

---

## 3. 测试方式说明

本次测试**全部为自动化测试**，共 64 个用例，分为两个文件：

| 文件 | 内容 | 用例数 |
| --- | --- | ---: |
| `tests/test_game.py` | 核心逻辑单元测试：方向、路径检测、边界、失误、状态流转、关卡校验 | 37 |
| `tests/test_app.py` | 通过模拟鼠标点击驱动**真实界面**，覆盖作业要求的 T01–T06 | 27 |

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

---

## 7. 测试有效性验证（变异测试）

"测试全部通过"本身不能说明测试有效——如果用例断言过弱，即使程序有 Bug 也会通过。
为确认测试确实能发现问题，人为注入三个典型缺陷，检查测试套件是否会失败：

| 注入的缺陷 | 说明 | 失败的用例数 | 结论 |
| --- | --- | ---: | --- |
| 忽略阻挡，永远返回"可飞出" | 完全不做路径检测 | 20 | ✅ 被捕获 |
| 只看紧邻一格 | 只检查箭头前方一格是否有阻挡 | 3 | ✅ 被捕获 |
| 边缘朝外误判为被阻挡 | 典型的越界处理错误 | 58 | ✅ 被捕获 |

三个变异全部被测试套件捕获，说明用例具备实际的检错能力。

---

## 8. 测试结果汇总

```text
Ran 64 tests in 2.686s

OK
```

| 项目 | 结果 |
| --- | --- |
| 用例总数 | 64 |
| 通过 | 64 |
| 失败 | 0 |
| 错误 | 0 |
| 作业要求测试 T01–T06 | 6 / 6 全部通过 |
| 发现的产品缺陷 | 1（已修复，已加回归测试） |

---

## 9. 未覆盖的部分

以下内容无法用自动化测试覆盖，由人工确认：

| 项目 | 说明 |
| --- | --- |
| 动画观感 | 飞出位移与碰撞晃动的视觉效果是否自然，需人工试玩判断 |
| 中文字体显示 | 测试只验证"能渲染不报错"；实际字形是否正确需人工查看 |
| 布局美观度 | 界面排版是否合理清晰，属主观判断 |
| 关卡难度体验 | 三个关卡的实际游玩难度与趣味性，需人工试玩 |
| 通关顺序合理性 | 已用求解器验证"存在通关顺序"，但顺序是否够巧妙仍需人工试玩 |
