# 移除 strips 选区，只保留面板（2026-11-25）

## 决定

删掉 `ui.selection` 与整条「无遮罩 4 条边框」选区链路，**只保留以鼠标为中心的面板选区**：

- 删除 `src/ocrsnip/win_rect.py`（Win32 低层钩子 + 4 个 `WS_POPUP` 小窗）
- 删除 `src/ocrsnip/x11_rect.py`（x11rect 的薄封装）
- 删除 `scripts/accept_strips.sh`、`tests/test_win_rect.py`
- ocrsnip 不再依赖 `x11rect`：其中**剪贴板多 target 与键盘 grab 探测**内联为 `src/ocrsnip/x11_clip.py`
- 配置项 `ui.selection` / `border_color` / `border_thickness` / `arm_timeout_sec` / `armed_hint` 一并移除

## 为什么

1. **两端行为要一致**：面板方案在 Linux(GTK) 与 Windows(Qt) 上都跑通了，交互相同。
2. **strips 的代价远超收益**：为了"不建全屏窗口"，Windows 侧要装系统级鼠标/键盘钩子、
   自己建 4 个窗口逐帧挪位置，真机上先后踩到钩子回调超时被摘、类背景刷不擦、`WS_EX_TRANSPARENT`
   不绘制、`UpdateWindow` 时序等问题；每修一处都引入新的不确定性。
3. **用户视角没有收益**：拖动时同样只有一圈框，但多了"按下点被固定"的橡皮筋语义争议。
4. **面板并不慢**：只抓面板那一小块（1/4 屏）比抓全屏快，冻结帧内存也小 4 倍。

## 代价与后续

- 失去"完全不弹窗口"的特性（面板会覆盖一小块屏幕，面板内是冻结画面）。
- `x11rect` 仍是独立仓库/包，只是 ocrsnip 不再依赖它；如需恢复无遮罩方案，代码在 git 历史里
  （`62beab4` 之前）。
- 想再回到 strips，请先解决本次记录里的 4 个真机问题，并补回对应用例。
