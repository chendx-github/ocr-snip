<#
  远程无人值守构建（deploy_windows.sh 会在 Windows 测试机上启动它）。
  全程写 windows\build.log，构建失败也不中断脚本，方便回看。

  产物：
    windows\dist\ocrsnip\ocrsnip.exe          绿色版
    windows\Output\ocrsnip-<ver>-setup.exe    安装包（装了 Inno Setup 6 才有）
#>
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root 'windows\build.log'
Remove-Item $log -ErrorAction SilentlyContinue

function Log([string]$message) {
    Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $message)
}

function Run-Step([string]$name, [scriptblock]$block) {
    Log "=== $name"
    $output = & $block 2>&1
    $code = $LASTEXITCODE
    foreach ($line in @($output)) { if ($null -ne $line) { Log "  $line" } }
    Log "=== $name 退出码 $code"
    return $code
}

Log "=== 环境"
Log (Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption)
Log "Python: $(& py -3 --version 2>&1)"
Log "磁盘剩余 GB: $([math]::Round((Get-PSDrive C).Free / 1GB, 1))"

# ---- 1. 虚拟环境 ------------------------------------------------------------
if (-not (Test-Path '.venv-build\Scripts\python.exe')) {
    Run-Step '创建 venv' { py -3 -m venv .venv-build }
}
$py = (Resolve-Path '.venv-build\Scripts\python.exe').Path

# ---- 2. 依赖 ---------------------------------------------------------------
$mirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'
$code = Run-Step '安装依赖（tuna 镜像）' {
    & $py -m pip install -U pip wheel -i $mirror --timeout 30
    & $py -m pip install -e '.[gui]' pyinstaller pytest -i $mirror --timeout 30
}
if ($code -ne 0) {
    # 官方源再试一次
    $code = Run-Step '安装依赖（官方源重试）' {
        & $py -m pip install -e '.[gui]' pyinstaller pytest --timeout 30
    }
}
if ($code -ne 0) { Log '!!! 依赖安装失败，终止'; exit 1 }

# ---- 3. 单元测试 -----------------------------------------------------------
Run-Step '单元测试' { & $py -m pytest -q }

# ---- 4. 自检 ---------------------------------------------------------------
Run-Step '源码自检' { & $py -m ocrsnip selftest --ui qt }

# ---- 5. PyInstaller --------------------------------------------------------
if (Test-Path 'windows\dist') { Remove-Item 'windows\dist' -Recurse -Force }
if (Test-Path 'windows\build') { Remove-Item 'windows\build' -Recurse -Force }
$code = Run-Step 'PyInstaller 打包' {
    & (Join-Path (Split-Path $py) 'pyinstaller.exe') windows\ocrsnip.spec --noconfirm --clean `
        --distpath windows\dist --workpath windows\build
}
if ($code -ne 0) { Log '!!! 打包失败，终止'; exit 1 }

# ---- 6. 打包产物冒烟 -------------------------------------------------------
Run-Step '绿色版冒烟（selftest）' { & 'windows\dist\ocrsnip\ocrsnip.exe' selftest --ui qt }

# ---- 7. 安装包（可选） ------------------------------------------------------
# 注意：Inno Setup 也常被装成"当前用户"（不需要管理员），必须三处都找
$iscc = @(
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Log '未找到 Inno Setup 6，尝试 winget 安装（失败不影响绿色版）'
    Run-Step 'winget 安装 Inno Setup' {
        winget install -e --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements --silent
    }
    $iscc = @(
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($iscc) {
    Run-Step '生成安装包' { & $iscc windows\installer.iss }
} else {
    Log '跳过安装包（没有 Inno Setup 6）'
}

Log '=== 完成'
Get-ChildItem 'windows\dist\ocrsnip\ocrsnip.exe', 'windows\Output' -ErrorAction SilentlyContinue |
    ForEach-Object { Log ("产物: {0}  {1:N1} MB" -f $_.FullName, ($_.Length / 1MB)) }
