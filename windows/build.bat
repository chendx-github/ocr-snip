@echo off
rem ==========================================================================
rem  ocrsnip Windows 打包脚本
rem
rem  在【仓库根目录的 windows\ 目录】里双击运行，或在命令行执行：windows\build.bat
rem  产物：windows\dist\ocrsnip\ocrsnip.exe（绿色版，整个 dist\ocrsnip 目录可拷走）
rem  如果装了 Inno Setup 6，会自动再生成 windows\Output\ocrsnip-0.3.0-setup.exe
rem ==========================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0.."

echo == 1. 检查 Python
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul || (echo 缺少 Python 3.10+：请先安装 https://www.python.org/downloads/windows/ & exit /b 1)
  set "PYRUN=python"
) else (
  set "PYRUN=py -3"
)

echo == 2. 建立打包用虚拟环境 .venv-build
if not exist .venv-build\Scripts\python.exe (
  %PYRUN% -m venv .venv-build || (echo 创建虚拟环境失败 & exit /b 1)
)
call .venv-build\Scripts\activate.bat

echo == 3. 安装依赖
python -m pip install -U pip wheel >nul || exit /b 1
python -m pip install -e ".[gui]" pyinstaller || (echo 依赖安装失败 & exit /b 1)

echo == 4. 自检（OCR 能否出字，避免打出个跑不起来的包）
python -m ocrsnip selftest --ui qt
if errorlevel 1 (
  echo [警告] 自检未通过，继续打包但请先排查 selftest 输出
)

echo == 5. PyInstaller 打包
if exist windows\dist rmdir /s /q windows\dist
if exist windows\build rmdir /s /q windows\build
pyinstaller windows\ocrsnip.spec --noconfirm --clean --distpath windows\dist --workpath windows\build
if errorlevel 1 (echo 打包失败 & exit /b 1)

echo == 6. 生成安装包（可选，需要 Inno Setup 6）
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  "%ISCC%" windows\installer.iss
) else (
  echo   未找到 Inno Setup 6，跳过安装包生成。
  echo   绿色版已就绪：windows\dist\ocrsnip\ocrsnip.exe
)

echo.
echo 完成。
echo   绿色版 : windows\dist\ocrsnip\ocrsnip.exe
if exist windows\Output echo   安装包 : windows\Output\
endlocal
