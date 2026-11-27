# PowerShell 5.1 读无 BOM 的 UTF-8 .ps1 会把中文啃成乱码并语法报错

日期：2026-11-21，Windows 10 19043（Windows PowerShell 5.1）。

## 现象

脚本报 `字符串缺少终止符: '。` / `无法将参数绑定到参数Path，因为它包含 Null`，
且错误信息里的中文全是乱码 —— 文件明明是 UTF-8。

原因：PowerShell 5.1 对**没有 BOM** 的 .ps1 按系统 ANSI（这里是 GBK）解码，
中文字节被拆坏，正好把引号/换行吃掉。

## 做法

仓库里所有 .ps1 一律 **UTF-8 with BOM**（`windows/*.ps1` 已加 BOM）。
临时脚本要么纯 ASCII，要么 `printf '\xef\xbb\xbf' | cat - script.ps1`。

## 同类坑（同日踩过）

- `Start-Process -ArgumentList 'a','b' + $x -Wait`：`+` 的优先级会让 `-Wait` 变位置参数 →
  先 `$a = @(..., ('/DIR=' + $dir))` 再传。
- 单引号里的 `$env:USERPROFILE` **不会展开**；要从 Linux 传命令给远端 PowerShell，
  最稳的做法是把脚本 scp 成 .ps1 再 `-File` 执行，别在命令行里套三层引号。
