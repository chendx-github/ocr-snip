# 从 SSH 驱动 Windows 测试机的三个坑

日期：2026-11-21，主机 `WIN125121_02395`（Windows 10 19043，OpenSSH，控制台会话属于同一用户）。

1. **`Start-Process` 起的进程会被 sshd 回收**：SSH 会话一断，子进程一起没了 —— 表现为
   "launched" 但 `build.log` 永远不存在。可靠做法：本机的 `ssh` 进程保持连接
   （`nohup ssh ... > /tmp/remote_build.out 2>&1 &`），远端就跑到底，另开连接轮志。
2. **GUI 不在控制台桌面上**：SSH 会话是 session 0，启动的托盘程序/浮层在控制台看不到。
   所以远程只能验到 `selftest`（OCR + 剪贴板 + Qt），热键与框选必须在真实会话里试。
3. **`Get-Content` 的编码**：PS 5.1 的 `Add-Content` 默认写 ANSI(GBK)，
   读取要按 GBK（在 Linux 侧管道 `iconv -f GBK -t UTF-8`），加 `-Encoding Unicode` 反而更乱。

## 顺带记录：winget 装 Inno Setup 失败

`winget install -e --id JRSoftware.InnoSetup --silent` 退出码 `-1978335189`（0x8A15002B）。
改成 `Invoke-WebRequest https://jrsoftware.org/download.php/is.exe` +
`/VERYSILENT /CURRENTUSER` 就装上了（不需要管理员）。

## Inno Setup 官方不带中文语言文件

`compiler:Languages\ChineseSimplified.isl` 属于非官方翻译包，官方安装里没有 →
`[Languages]` 里写它会直接编译失败。installer.iss 已改成只依赖 `Default.isl`，
自定义文案本身写中文即可。
