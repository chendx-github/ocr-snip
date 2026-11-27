# 自启动是怎么配的（2026-11-19 验证）

结论先说：**不是开机自启，是登录图形会话后自启** —— 开机时没有 X11，热键工具没意义。

## 两处配置，互为兜底

1. `~/.config/systemd/user/ocrsnip.service`，`WantedBy=default.target`（enabled）
   - ⚠️ 最初写的是 `WantedBy=graphical-session.target`，**在 Cinnamon/X11 下永远不会被触发**：
     实测 `systemctl --user is-active graphical-session.target` = `inactive`，
     `UnitFileState=static`。Cinnamon 不上报这个 target（那是 GNOME/Wayland 的约定）。
   - 用户会话里真正会被激活的是 `default.target`（→ `basic.target`），所以改成它。
2. `~/.config/autostart/ocrsnip.desktop`，`Exec=systemctl --user start ocrsnip.service`
   - Cinnamon 登录时会执行 XDG autostart；它只是把服务再拉一次，`start` 是幂等的。

## 第二个坑：登录时 DISPLAY 还没进 systemd 用户环境

`PassEnvironment=DISPLAY` 只在 systemd 用户管理器里**已经有** DISPLAY 时才有效；
重启后它是空的。于是 daemon 自己找 display：`src/ocrsnip/display_env.py`
扫 `/tmp/.X11-unix/X*`，优先 `:0`，用 python-xlib 试连，最多重试 20 秒。

验证方式（模拟重启后的环境）：

```bash
systemctl --user stop ocrsnip
systemctl --user unset-environment DISPLAY XAUTHORITY XDG_SESSION_TYPE
systemctl --user start ocrsnip
journalctl --user -u ocrsnip -n 5 -o cat
# 预期：WARNING DISPLAY 未设置/不可用（None），自动使用 :0
```

实测通过：热键注册成功、面板正常唤出。测完记得
`systemctl --user import-environment DISPLAY XAUTHORITY`，否则其它用户级图形服务也会缺 DISPLAY。

## 自启的三重保险

| 层 | 机制 | 作用 |
| --- | --- | --- |
| 1 | `default.target.wants/ocrsnip.service` | 登录时 systemd 拉起，带 `Restart=on-failure` |
| 2 | `~/.config/autostart/ocrsnip.desktop` | 万一 target 没触发，桌面环境再拉一次（幂等） |
| 3 | 单实例锁 `sock-<DISPLAY>.lock` | 两层同时拉起也只活一个，第二个退出 0 |
