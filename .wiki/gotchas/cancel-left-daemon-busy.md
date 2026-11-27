# Esc 取消后没通知 daemon，`busy` 永远为真 → 之后热键全部静默失效

日期：2026-11-19。ocrsnip 0.2.0 修掉的真 bug（用户反馈"按了没反应"）。

## 现象

面板能用一次；按 Esc 取消之后，再按热键**完全没反应**，日志里连一行都没有。
`ocrsnip status` 的 `busy` 一直是 `true`。

## 根因

浮层有两条结束路径，只有一条会通知 daemon：

```python
def _finish(self):
    self._done = True      # ← 先置位
    self.destroy()         # → 触发 destroy 信号

def _on_destroy(self, _w):
    if not self._done:     # ← 永远为 False
        self._on_cancel()  # ← 于是 daemon 收不到取消通知
```

选中路径会回调 `on_selected`，所以"选一次"能用；取消路径谁也没告诉 daemon，
daemon 的 `_busy` 停在 True，`trigger()` 直接 return。

## 修法

1. `_finish()` 在 destroy **之后**显式调用 `self._on_cancel()`；`_on_destroy` 只做兜底。
2. daemon 用**在途计数器** `_inflight` 替代布尔 `_busy`：触发 +1，取消/复制/报错各 -1。
   一条路径漏了也只是泄漏计数，不会像布尔那样"一旦错就一直错"。
3. 加 120s 看门狗：`_inflight > 0` 且没有浮层窗口超过 2 分钟就强制复位并 WARNING。
4. `scripts/e2e.sh` 第 5 步专门回归这个：热键 → Esc → 热键，第二次必须还能唤出面板。

## 教训

凡是"窗口/线程告诉我结束了"的路径，必须保证 **恰好通知一次**，
并且用计数器而不是布尔做幂等保护。

## 后续（2026-11-21）：`ocrsnip stop` 会永久停掉服务

用户反馈"本机的不能用了"。原因：我在一个 `DISPLAY=:0` 的 shell 里执行了
`ocrsnip stop`（本意是停 Xvfb 上的测试实例），unix socket 按 DISPLAY 分名，
所以这一发打到了正式实例；而单元是 `Restart=on-failure`，进程**退出码 0**
不算失败 → 不会自动拉起 → 热键彻底没反应。

修法：单元改 `Restart=always` + `[Unit] StartLimitIntervalSec=0`。
以后 `ocrsnip stop` 只相当于"重启一下"，真要停必须 `systemctl --user stop ocrsnip`。

顺带：`StartLimitIntervalSec` 写在 `[Service]` 里 systemd 会告警忽略，必须放 `[Unit]`。
