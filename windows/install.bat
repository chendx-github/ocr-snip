@echo off
rem ==========================================================================
rem  ocrsnip 一键安装（需要本机已有 Python 3.10+）
rem
rem  双击即可：建独立 venv → 装依赖 → 写配置 → 建快捷方式+自启动 → 启动托盘程序
rem  装到 %LOCALAPPDATA%\ocrsnip（不需要管理员权限）
rem  卸载：windows\uninstall.bat
rem ==========================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0.."

set "TARGET=%LOCALAPPDATA%\ocrsnip"
set "VENV=%TARGET%\venv"

echo == 1. 检查 Python
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul || (
    echo 缺少 Python 3.10+。
    echo 方案一：安装 Python ^(https://www.python.org/downloads/windows/^) 后重新运行本脚本
    echo 方案二：用 windows\build.bat 打包成 ocrsnip-setup.exe，在没有 Python 的机器上安装
    pause & exit /b 1
  )
  set "PYRUN=python"
) else (
  set "PYRUN=py -3"
)
%PYRUN% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" || (
  echo Python 版本过低，需要 3.10 及以上 & pause & exit /b 1
)

echo == 2. 建立虚拟环境 %VENV%
if not exist "%VENV%\Scripts\python.exe" (
  %PYRUN% -m venv "%VENV%" || (echo 创建虚拟环境失败 & pause & exit /b 1)
)
call "%VENV%\Scripts\activate.bat"

echo == 3. 安装依赖（首次约 200MB，需要联网）
python -m pip install -U pip wheel >nul || goto :fail
python -m pip install -e ".[gui]" || goto :fail

echo == 4. 写默认配置
python -m ocrsnip config --init || echo   （配置已存在，跳过）

echo == 5. 自检
python -m ocrsnip selftest --ui qt || echo   [警告] 自检未通过，可稍后用 `ocrsnip doctor` 排查

echo == 6. 快捷方式与自启动
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register.ps1" -Target "%TARGET%"

echo == 7. 启动
start "" "%VENV%\Scripts\ocrsnipw.exe" daemon --ui qt
echo.
echo 完成：托盘里应出现图标，按 Ctrl+Alt+Q 即可框选识别。
echo   配置：%APPDATA%\ocrsnip\config.toml
echo   日志：%LOCALAPPDATA%\ocrsnip\ocrsnip.log
goto :eof

:fail
echo.
echo 安装失败，请把上面的报错发出来。
pause
exit /b 1
