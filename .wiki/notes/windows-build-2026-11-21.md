# Windows 实机构建与验证（2026-11-21，WIN125121_02395）

机器：Windows 10 专业版 19043，Python 3.12.0，C 盘剩余 15.7 GB，32 GB 内存。
（原计划用的 Win11 测试机当时 ping 不通，改用了 Win10 测试机。）

## 结果

| 步骤 | 结果 |
| --- | --- |
| 依赖安装（tuna 镜像） | 退出码 0（官方 pypi 卡住 15 分钟没进展，换镜像后 17 秒装完） |
| `pytest -q` | 退出码 0 |
| 源码 `selftest --ui qt` | 通过：识别出 `ocrsnip 自检 OCR 1234`，剪贴板可用；预热 1983 ms，识别 263 ms |
| PyInstaller onedir | 退出码 0，`windows\dist\ocrsnip` = 306 MB |
| 绿色版 exe 冒烟 | 退出码 0 |
| Inno Setup | winget 失败 → 直连下载 + `/CURRENTUSER` 装上 → 编译成功 |
| `ocrsnip-0.3.0-setup.exe` | 94 MB，MD5 `533e54a34f8772ecc8fafdbdcffcc5ef` |
| 绿色版 zip | 130 MB，MD5 `879e6c8af7020158a7077d85acf32aa8` |
| **静默安装→安装后 exe 自检→卸载** | 安装 310 MB，自检通过，卸载后目录干净 |

产物已回传到 Linux 侧 `releases/`（含 `windows-build.log`）。

## 还没验的部分

**热键与框选浮层**必须在真实交互桌面里测：SSH 是 session 0，GUI 不上屏（见 gotchas/windows-ssh-quirks.md）。
下一步应在用户的 Win11 上装 `ocrsnip-0.3.0-setup.exe` 后按 `Ctrl+Alt+Q` 验一次。

## 慢机器的启示

该机器预热 2.0s / 识别 263ms（本机 0.6s / 60ms）。所以"预热一次、进程常驻"的设计是必要的；
如果目标机器更慢，可以考虑把 `threads` 调到物理核数、或降低 `det_limit_side_len`。
