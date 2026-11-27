# `pkill -f "ocrsnip --config ..."` 会杀掉自己

日期：2026-11-19。踩过两次，两次都表现为整条命令 exit 143。

原因：`pkill -f` 匹配的是完整命令行，而当前这条 `bash -c "... pkill -f 'ocrsnip --config /tmp/e2e' ..."`
自身就包含该字符串，于是把自己杀了（顺带把同一命令里后面的步骤全丢）。

## 做法

- 优先用 `ocrsnip stop`（走 socket）而不是 pkill。
- 确实要 pkill 时用方括号技巧：`pkill -f "[o]crsnip --config"`。
- 清理 Xvfb 用 `pgrep -f "[X]vfb :9"` 再逐个 kill。
