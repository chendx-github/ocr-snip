# 启动无人值守构建（detached）。deploy_windows.sh 会用到。
$script = Join-Path $env:USERPROFILE 'ocrsnip-src\windows\build_remote.ps1'
if (-not (Test-Path $script)) { throw "找不到 $script" }
Start-Process powershell -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script
) -WindowStyle Hidden
Write-Output ("launched: " + $script)
