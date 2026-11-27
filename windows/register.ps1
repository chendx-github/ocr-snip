<#
  建快捷方式 + 自启动（当前用户，无需管理员）

  用法（install.bat 会自动调用）：
    powershell -NoProfile -ExecutionPolicy Bypass -File windows\register.ps1 -Target "$env:LOCALAPPDATA\ocrsnip"

  做三件事：
    1. 开始菜单快捷方式 → venv\Scripts\ocrsnipw.exe daemon --ui qt
    2. 启动文件夹快捷方式（登录后自动拉起托盘程序）
    3. 桌面快捷方式（存在才创建，不覆盖用户自定义）
#>
param(
    [Parameter(Mandatory = $true)][string]$Target,
    [switch]$NoStartup,
    [switch]$NoDesktop
)

$ErrorActionPreference = 'Stop'
$exe = Join-Path $Target 'venv\Scripts\ocrsnipw.exe'
if (-not (Test-Path $exe)) { throw "找不到 $exe，请先运行 install.bat" }

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param([string]$Path, [string]$Description)
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $exe
    $shortcut.Arguments = 'daemon --ui qt'
    $shortcut.WorkingDirectory = $Target
    $shortcut.Description = $Description
    $shortcut.IconLocation = "$exe,0"
    $shortcut.WindowStyle = 7  # 最小化启动，不闪窗口
    $shortcut.Save()
    Write-Host "   已创建 $Path"
}

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-Shortcut -Path (Join-Path $startMenu 'ocrsnip.lnk') -Description 'ocrsnip 热键框选 OCR'

if (-not $NoStartup) {
    $startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
    New-Shortcut -Path (Join-Path $startup 'ocrsnip.lnk') -Description '登录后自动启动 ocrsnip'
}

if (-not $NoDesktop) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $link = Join-Path $desktop 'ocrsnip.lnk'
    if (-not (Test-Path $link)) {
        New-Shortcut -Path $link -Description 'ocrsnip 热键框选 OCR'
    }
}

Write-Host '   自启动/快捷方式就绪（登录后托盘常驻，热键 Ctrl+Alt+Q）'
