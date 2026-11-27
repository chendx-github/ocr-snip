> **已被取代（2026-11-25）**：strips 选区已移除，只保留面板，见 [panel-only-after-removing-strips.md](panel-only-after-removing-strips.md)。本页仅作历史记录。

# Windows 为什么不用"全屏透明窗"，而用低层钩子 + 4 条边框

日期：2026-11-24。ocrsnip 0.3.x，实机验证机 `WIN125121_02395`（Win10 19043）。

## 三条路的对比

| 方案 | 效果 | 代价 |
| --- | --- | --- |
| `WS_EX_LAYERED` + key-color 透明全屏窗 | 只有边框可见 | **key-color 区域点击穿透** → 收不到第一次按下；要收点击就得画不透明像素 |
| `WS_EX_LAYERED` + alpha≈1 全屏窗 | 几乎看不出蒙层 | 等于给全屏加 1/255 蒙层；layered 窗口背后要维护全屏位图（4K ≈ 33MB 全程驻留） |
| **`WH_MOUSE_LL` 钩子 + 4 个 `WS_POPUP` 小窗** | 屏幕上除边框无本进程窗口 | 选区期间装系统级鼠标/键盘钩子（臂章 12s、拖动 45s 上限，结束立即卸） |

选第三种：和 X11 那边的 strips 方案同构，视觉效果一致（零遮罩），内存只有冻结帧
（4K ≈ 33MB，选完就 `DeleteObject` 释放），没有常驻全屏 surface。

## 关键实现细节（都在真机上踩过）

1. `GetModuleHandleW` 在 **kernel32**，不在 user32 —— 写错就是 `function not found`。
2. 64 位下所有 HANDLE 必须声明 `restype`：`CreateWindowExW`/`CreateDIBSection`/`GetDC`/
   `SetWindowsHookExW`/`GlobalAlloc`… 不声明会被 ctypes 当 32 位 int **静默截断**。
3. `ctypes.wintypes.WNDCLASSW` **不存在**，要自己定义结构体；`ctypes.WINFUNCTYPE` 仅 Windows 有，
   Linux 上 import 本模块必须能过（用 `getattr(ctypes, "WINFUNCTYPE", CFUNCTYPE)` 兜底）。
4. 冻结：`GetDC(NULL)` + `CreateDIBSection`（`biHeight = -h`，top-down）+ `BitBlt`。
   像素在内存里是 **BGRA**，正好可以零拷贝 `np.frombuffer`，取前三通道就是 rapidocr 要的 BGR。
   `c_char` 数组是 int8，必须按 uint8 解释，否则颜色变负数。
5. **超时**：钩子回调里不能阻塞，也不能自己开线程等；用 `SetTimer(None, id, 100, None)`
   在消息循环里处理 `WM_TIMER` 检查 deadline（按下前 `arm_timeout`，按下后 `timeout`）。
   第一版忘了这一步 → 没人点击就永久挂住（真机上抓到的）。
6. 剪贴板：Windows 天然支持一份内容多种格式，所以一次放 `CF_UNICODETEXT` + `CF_DIB` + 注册格式
   `PNG`；`CF_DIB` 要**自底向上**（把行翻转）并补 alpha，很多老程序（画图）只认它。

## 验证（真机）

```
== 1. 冻结整屏（BitBlt -> DIB）
   1024x768 stride=4096 冻结耗时 0.2 ms
   PNG 82 B, DIB 20040 B
== 2. 装 hook + 建 4 条边框窗，2 秒无人操作应超时返回 None
   result=None 耗时 2070 ms
== 3. 剪贴板多格式
   写入格式: text+dib+png
   剪贴板上存在的格式: [(13, True), (8, True), ('PNG', True)]
```

注意：SSH 会话是 session 0，桌面是 1024x768 的黑屏，所以"冻结耗时 0.2ms"偏乐观
（4K 真桌面大约 10–20ms）；**真实拖框体验必须在交互桌面里验**。

单测（跨平台跑的纯逻辑，8 例）：BGRA 通道顺序、top-down 行序、带 padding 的 stride、
越界/反向/空选区、`to_png` 往返、CF_DIB 头部字段与行翻转、BGR 输入补 alpha。
