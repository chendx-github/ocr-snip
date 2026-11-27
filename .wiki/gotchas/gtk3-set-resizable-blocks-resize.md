# `set_resizable(False)` 会让之后所有 `resize()` 被忽略（浮层只剩左上角 200×200）

日期：2026-11-19。ocrsnip 0.1.0 → 0.2.0 之间修掉的真 bug。

## 现象

用户反馈"框选浮层只能在左上角，而且很小"。`xdotool getwindowgeometry` 显示：

```
Position: 427,476        # move() 生效了
Geometry: 200x200        # 但 resize() 完全没生效
```

`move()` 正确、`resize()` 无效 —— 因为 `__init__` 里写了 `self.set_resizable(False)`。
GTK3 把这当成"固定尺寸窗口"，之后所有程序化 resize 都被丢掉，窗口保持默认 200×200。

## 修法

不设 `set_resizable(False)`（无边框窗口本来也没有拖拽边框，用户改不了大小），
改成 `set_default_size(w, h)` + `set_size_request(w, h)`，并在 `open()` 里
move → resize → show_all → **再 resize + move 一次**（有些 WM 要等 map 之后才认）。

## 附带发现

同一台机器是 3840×1080 双屏，早先"整屏浮层"的尝试里 `resize(3840,1080)` 也被忽略了，
所以用户看到的是主屏左上角一块 —— 两个问题叠加。现在改成"以鼠标为中心、约 1/4 屏的面板"，
尺寸始终 ≤ 单个显示器，天然避开 WM 与跨屏限制。
