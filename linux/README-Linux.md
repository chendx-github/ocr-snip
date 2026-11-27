# ocrsnip for Linux

按 `Ctrl+Alt+Q` → 鼠标附近弹出冻结画面面板 → 拖一个框 → 框里的文字直接进剪贴板。

自带运行时（Python + Qt + OCR 模型），**不需要**系统里装 GTK / PyGObject / Python 包。
界面后端是 Qt（PySide6）；全局热键走 X11 `XGrabKey`。

---

## 一、三种装法（挑一个）

### 方式 A：AppImage 单文件（最省事，免安装）

```bash
chmod +x ocrsnip-0.3.0-x86_64.AppImage
./ocrsnip-0.3.0-x86_64.AppImage daemon     # 前台跑，按 Ctrl+Alt+Q 即可用
```

想开机自启，把文件放到固定位置（例如 `~/Applications/ocrsnip.AppImage`），再给它建一个自启项：

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/ocrsnip.desktop <<'D'
[Desktop Entry]
Type=Application
Name=ocrsnip
Exec=%h/Applications/ocrsnip.AppImage daemon
Terminal=false
X-GNOME-Autostart-enabled=true
D
```

> 没装 FUSE 的系统（少部分容器/精简发行版）改用：
> `./ocrsnip-0.3.0-x86_64.AppImage --appimage-extract-and-run daemon`

### 方式 B：通用绿色版（任意发行版，不需要 root）

```bash
tar xzf ocrsnip-0.3.0-linux-x64.tar.gz
cd ocrsnip-0.3.0-linux-x64
./install.sh            # 装到 ~/.local/opt/ocrsnip，注册 systemd 用户服务 + 桌面自启
```

- 只装了文件不想要服务：`./install.sh --no-service`
- 卸载：`~/.local/opt/ocrsnip/uninstall.sh`（保留配置）

### 方式 C：deb（Debian / Ubuntu / Mint / 深度 等）

```bash
sudo apt install ./ocrsnip_0.3.0_amd64.deb
/opt/ocrsnip/enable-autostart.sh     # 让当前用户登录后自动启动（只影响你自己）
```

卸载：`sudo apt remove ocrsnip`

---

## 二、系统要求（很低）

| 项 | 要求 |
|---|---|
| 架构 | x86_64 |
| C 库 | **glibc ≥ 2.38**（实测：包里 `libpython3.12.so` 需要 2.38；本包在 Mint 22.3 / glibc 2.39 上构建） |
| 显示服务 | **X11**（Xorg / XWayland 均可；纯 Wayland 下热键不生效） |
| 系统库 | `libgl1 libegl1 libglvnd0 libglx0 libxcb1`，外加 **`libxcb-cursor.so.0`**（Qt 6.5+ 的 xcb 平台插件硬依赖：Debian 系叫 `libxcb-cursor0`，RHEL/Rocky 8 只能用 EPEL 的 `xcb-util-cursor`。构建时会自动取一份打进 `_internal/`，见第五节） |
| 可选 | `xclip`（剪贴板兜底）、`xdotool`（`auto_paste = true` 时用） |

按这个底线，能直接跑的系统：**Ubuntu 24.04+、Linux Mint 22+、Debian 13+、Fedora 39+、
RHEL/Alma/Rocky 10+、Arch / openSUSE Tumbleweed（滚动版都行）**。

> 老一些的系统（Ubuntu 22.04 / Debian 12 / Mint 21）用当前包会报
> `GLIBC_2.38 not found` —— 需要在老系统里重新构建：
> `./linux/build_in_container.sh`（在 ubuntu:22.04 容器里构建，底线降到 2.35；
> 本机因公司代理拦了容器仓库，这个脚本没法在这儿代跑）。
>
> 连容器都没有的老系统（例如 Rocky/RHEL 8，glibc 2.28）直接用源码构建就行：
> `./linux/build_app.sh` 出来的产物按本机 glibc 链接，不再有 2.38 的坎。
> 实测 Rocky 8.10 / glibc 2.28 / X11：构建通过，抓屏 8 ms、OCR 25–79 ms、
> 热键→框选→剪贴板端到端跑通；同一台机器上官方 AppImage 因为 2.38 底线直接起不来。

---

## 三、日常使用

| 操作 | 说明 |
|---|---|
| `Ctrl+Alt+Q` | 呼出面板（在配置文件里可改） |
| 左键拖框 | 框内文字进剪贴板；图片也同时放在剪贴板里 |
| `Esc` / 右键 | 取消 |
| `ocrsnip doctor` | 自检：热键、抓屏、OCR 预热耗时 |
| `ocrsnip status` | 守护进程状态 |
| `journalctl --user -u ocrsnip -f` | 实时日志 |

配置文件：`~/.config/ocrsnip/config.toml`（`ocrsnip config` 可生成带注释的模板）。
面板大小三种给法：`fullscreen = true` / `panel_width+panel_height` / `panel_scale`。

---

## 四、常见问题

| 现象 | 原因/处理 |
|---|---|
| 按热键没反应 | 会话被锁屏、或有程序（截图/剪贴板工具）持有键盘 grab；解锁或退出那个程序即可。`ocrsnip doctor` 会报热键状态 |
| 面板里是黑图 | 用了 Wayland 会话（需要在 XWayland 下运行，或登录时选 Xorg） |
| 提示 `libGL.so.1: cannot open` | 装 `libgl1 libegl1` |
| 启动报 `libpython3.12.so.1.0: version 'GLIBC_2.38' not found`（AppImage / 预编译包） | 预编译包是在 glibc 2.39 机器上构建的，底线 2.38；glibc < 2.38 的系统（Ubuntu 22.04 / Debian 12 / Rocky 8 …）只能本地构建，见第五节 |
| `Could not load the Qt platform plugin "xcb"`，或日志里出现 `From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed` | 缺 `libxcb-cursor.so.0`。`./linux/build_app.sh` 会自动取一份打进产物；手工装：Debian 系 `sudo apt install libxcb-cursor0`，RHEL/Rocky 8 用 `sudo dnf install --enablerepo=epel xcb-util-cursor` |
| 想开机自启但没生效 | `systemctl --user enable ocrsnip` 后再 `systemctl --user start ocrsnip` |

---

## 五、从源码构建

```bash
./linux/build_app.sh       # PyInstaller onedir → linux/dist/ocrsnip/（自带 Python+Qt+模型）
./linux/build_pkg.sh       # → releases/ocrsnip-<ver>-linux-x64.tar.gz
                           #   releases/ocrsnip_<ver>_amd64.deb
./linux/build_appimage.sh  # → releases/ocrsnip-<ver>-x86_64.AppImage（首次会下载 appimagetool）
./linux/build_in_container.sh   # 想在老系统上跑：在 ubuntu:22.04 容器里构建
```

构建会先跑 `./linux/fetch_vendor_libs.sh`：系统里没有 `libxcb-cursor.so.0` 时，
它从发行版仓库把包下下来、只取出那个 `.so` 放进 `linux/vendor/lib/`（不需要 root，
也就不用为了一个库去动系统），随后由 `linux/ocrsnip.spec` 打进产物的 `_internal/`。
取不到只警告、不阻断构建——目标机器自带该库就没问题。也可以单独跑它。

产物体积参考（0.3.0）：tar.gz 198 MB / deb 156 MB / AppImage 184 MB
（其中 OpenCV 172 MB、onnxruntime 69 MB、PySide6 100 MB、OCR 模型 31 MB）。
