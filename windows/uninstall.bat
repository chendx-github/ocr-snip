@echo off
rem 卸载 ocrsnip（install.bat 装的版本）
chcp 65001 >nul
setlocal
set "TARGET=%LOCALAPPDATA%\ocrsnip"

echo == 1. 结束正在运行的实例
taskkill /IM ocrsnipw.exe /F >nul 2>nul
taskkill /IM ocrsnip.exe /F >nul 2>nul

echo == 2. 删除快捷方式与自启动
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\ocrsnip.lnk" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ocrsnip.lnk" >nul 2>nul
del "%USERPROFILE%\Desktop\ocrsnip.lnk" >nul 2>nul

echo == 3. 删除程序目录（配置 %APPDATA%\ocrsnip\config.toml 保留）
if exist "%TARGET%\venv" rmdir /s /q "%TARGET%\venv"

echo.
echo 已卸载。要连配置和日志一起删，再执行：
echo   rmdir /s /q "%APPDATA%\ocrsnip"
endlocal
