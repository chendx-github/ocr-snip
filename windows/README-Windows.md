# ocrsnip for Windows

按下 `Ctrl+Alt+Q` → 鼠标附近弹出冻结画面面板（约 1/4 屏）→ 拖一个框 → 框里的文字直接进剪贴板。
托盘常驻、无控制台窗口、约 200–300 MB 内存、日常识别 **几十毫秒**。

界面后端用的是 **Qt（PySide6）**：全局热键走 `RegisterHotKey`，剪贴板走 Win32 多格式，
选区是「以鼠标为中心的面板」：`QScreen.grabWindow` 只抓面板那一小块 + Qt 无边框窗口。

> 2026-11-25 起移除了「无遮罩 4 条边框」（`ui.selection = "strips"`，低层钩子 + `WS_POPUP` 小窗）：
> 两端统一用面板，行为稳定、无钩子/自绘窗口的坑。

---

## 一、怎么装（三种方式，按你的情况选）

### 方式 A：有安装包（推荐给最终用户）

拿 `ocrsnip-0.3.0-setup.exe` 双击安装。安装时可勾选：

- **创建桌面快捷方式**
- **开机登录后自动启动**（写当前用户 Run 键，不需要管理员）

装完托盘出现图标，按 `Ctrl+Alt+Q` 即可用。

> 已构建并验证过的产物（2026-11-21，Windows 10 19043 测试机）：
>
> | 文件 | 大小 | MD5 |
> | --- | --- | --- |
> | `ocrsnip-0.3.0-setup.exe` | 94 MB | `533e54a34f8772ecc8fafdbdcffcc5ef` |
> | `ocrsnip-win-x64-portable.zip`（绿色版） | 130 MB | `879e6c8af7020158a7077d85acf32aa8` |
>
> 现成产物在 Linux 侧 `releases/`。自己构建：`windows\build.bat`，
> 或 GitHub Actions（`.github/workflows/build-windows.yml`）。
> ⚠️ 未做代码签名，首次运行会被 SmartScreen 拦一下：**更多信息 → 仍要运行**。

### 方式 B：本机已有 Python 3.10+（一条命令装好）

```bat
windows\install.bat
```

它会：建独立 venv（`%LOCALAPPDATA%\ocrsnip\venv`）→ 装依赖 → 写默认配置 → 跑自检 →
建开始菜单/启动文件夹快捷方式 → 启动托盘程序。全程不需要管理员权限。

卸载：`windows\uninstall.bat`（配置和日志默认保留）。

### 方式 C：自己跑源码（开发用）

```bat
py -3 -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
python -m ocrsnip selftest --ui qt     # 先确认 OCR 能出字
python -m ocrsnip daemon --ui qt       # 前台跑，日志直接看窗口
```

---

## 二、用法

| 操作 | 说明 |
| --- | --- |
| `Ctrl+Alt+Q` | 进入**无遮罩选区**：屏幕上什么都不出现，按下左键才冻结画面 |
| 拖动 | 框选，松手立刻识别并复制 |
| `Esc` / 右键 | 取消 |
| 托盘右键 | 立即截屏 / 打开配置 / 退出 |
| 再启动一次 exe | 不会开第二个实例，而是转发一次"截屏"（单实例） |

想框别处的文字：移动鼠标 → 再按一次热键，面板跟着鼠标走。
面板尺寸三种给法，优先级 `fullscreen` > `panel_width/panel_height` > `panel_scale`：

```toml
[ui]
fullscreen = false   # true = 面板占满鼠标所在显示器（整屏冻结画面）
panel_width = 0      # 显式宽（像素）；0 = 按 panel_scale 折算
panel_height = 0     # 显式高（像素）；0 = 按 panel_scale 折算
panel_scale = 0.5    # 边长占显示器比例；0.5 => 1/4 屏面积，1.0 => 整个显示器
```

例：想要固定 1200×800 的面板 → `panel_width = 1200`、`panel_height = 800`；
想要整屏 → `fullscreen = true`（等价于 `panel_scale = 1.0`，但意图更明确）。

## 三、配置与日志

| 文件 | 位置 |
| --- | --- |
| 配置 | `%APPDATA%\ocrsnip\config.toml` |
| 日志 | `%LOCALAPPDATA%\ocrsnip\ocrsnip.log` |

```toml
hotkey = "ctrl+alt+q"      # 支持 ctrl/alt/shift/win + 单键，例如 "ctrl+alt+a"、"print"
[ocr]
det_limit_side_len = 1024  # 最重要的性能开关，别改回 min
threads = 8
use_cls = false
[post]
mode = "smart"             # lines(保留换行) | smart(接回自动换行) | paragraph
strip_cjk_spaces = true
[clipboard]
auto_paste = false         # true 则复制后自动 Ctrl+V
[ui]
fullscreen = false         # true = 面板占满鼠标所在显示器
panel_width = 0            # 显式面板宽（像素）；0 = 按 panel_scale
panel_height = 0           # 显式面板高（像素）；0 = 按 panel_scale
panel_scale = 0.5          # 面板边长占显示器比例；0.5 => 1/4 屏面积
toast_ms = 1100
```

改完配置要重启程序（托盘 → 退出，再启动）。

## 四、打包（做出安装包）

```bat
windows\build.bat
```

步骤：建 `.venv-build` → 装依赖 → `selftest` → PyInstaller（**onedir**，启动快）→
若装了 [Inno Setup 6](https://jrsoftware.org/isdl.php) 再编译出 `windows\Output\ocrsnip-0.3.0-setup.exe`。

产物：

- 绿色版：`windows\dist\ocrsnip\ocrsnip.exe`（整个 `dist\ocrsnip` 目录可拷到别的机器直接用）
- 安装包：`windows\Output\ocrsnip-0.3.0-setup.exe`

不想装 Windows 工具链也行：把仓库推到 GitHub，手动跑一次 **build-windows** workflow，
从 Actions 里下载 `ocrsnip-windows` artifact。

## 五、排错

| 现象 | 处理 |
| --- | --- |
| 按热键没反应 | 看日志里有没有"热键已注册"；被其它软件占用时日志会写"注册失败（错误码 1409）"，换个 `hotkey` |
| 托盘没图标 | 日志 `%LOCALAPPDATA%\ocrsnip\ocrsnip.log`；常见是缺 VC++ 运行库 |
| 识别出来是空的 | 面板只覆盖 1/4 屏，确认文字在面板范围内；或把 `panel_scale` 调大 / 用 `fullscreen = true` |
| 高缩放屏（125%/150%）位置偏 | 已按 `devicePixelRatio` 换算，若仍偏请把 `ocrsnip doctor` 输出发出来 |
| 按热键后觉得"没反应" | 这是无遮罩模式的设计：**没有任何视觉反馈**，只有光标变十字；按下左键才会冻结画面。按 Esc 或等 12 秒（`ui.arm_timeout_sec`）自动取消 |
| 首次识别慢 | 模型加载只在启动时一次（测试机上预热 2.0s、识别 263ms；我本机 0.6s / 60ms）。慢机器建议保持托盘常驻 |
| SmartScreen 拦截 | 未签名，属预期：更多信息 → 仍要运行 |

命令行诊断（在装了 Python 的方式下可用）：

```bat
python -m ocrsnip doctor --ui qt      :: 平台 / 显示器 / 抓屏 / OCR 耗时 / 运行状态
python -m ocrsnip selftest --ui qt    :: 只要 OCR 通路
python -m ocrsnip status              :: 运行中实例的状态与上次耗时
python -m ocrsnip stop                :: 停掉托盘实例
```

## 六、已知限制

- 仅 **Windows 10/11 x64**（`x64compatible`）；未做 ARM64 与 Win7
- 安装包**未签名**，会触发 SmartScreen
- 同一组合键全局唯一：与其它软件冲突时换键
- Windows 没有 PRIMARY 选区，`clipboard.also_primary` 在 Windows 上无效果
- 打包体积约 150–200 MB（PySide6 + onnxruntime + OCR 模型），onxx 模型随包自带，无需联网下载
