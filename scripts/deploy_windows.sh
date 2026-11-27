#!/usr/bin/env bash
# 把源码推到 Windows 测试机并执行构建/自检。
#
# 用法：
#   scripts/deploy_windows.sh <server-key> [build|install|selftest]
#
# server-key 取 ssh-manager 配置里的键名（你自己在 MCP 里配好的服务器别名）。
# 需要：sshpass（密码登录）或 ssh-manager 配置里的 KEYPATH（密钥登录）。
#
# 说明：本脚本只做"传源码 + 远程跑 windows\build.bat / install.bat"，
# 不自动碰注册表/开始菜单之外的东西。
set -euo pipefail

KEY="${1:?用法: deploy_windows.sh <server-key> [build|install|selftest]}"
ACTION="${2:-build}"
ENV_FILE="$HOME/.ssh-manager/.env"

host=$(grep -E "^SSH_SERVER_${KEY}_HOST=" "$ENV_FILE" | cut -d= -f2- | tr -d '"')
user=$(grep -E "^SSH_SERVER_${KEY}_USER=" "$ENV_FILE" | cut -d= -f2- | tr -d '"')
port=$(grep -E "^SSH_SERVER_${KEY}_PORT=" "$ENV_FILE" | cut -d= -f2- | tr -d '"'); port=${port:-22}
pass=$(grep -E "^SSH_SERVER_${KEY}_PASSWORD=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)
keypath=$(grep -E "^SSH_SERVER_${KEY}_KEYPATH=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' || true)

[ -n "$host" ] || { echo "ssh-manager 里没有 $KEY"; exit 1; }

SSH_OPTS=(-p "$port" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
if [ -n "$keypath" ] && [ -f "$keypath" ]; then
  SSH_OPTS+=(-i "$keypath" -o BatchMode=yes)
elif [ -n "$pass" ]; then
  export SSHPASS="$pass"
  SSH() { sshpass -e ssh "${SSH_OPTS[@]}" "$user@$host" "$@"; }
  SCP() { sshpass -e scp -P "$port" -o StrictHostKeyChecking=accept-new "$@"; }
else
  SSH() { ssh "${SSH_OPTS[@]}" "$user@$host" "$@"; }
  SCP() { scp -P "$port" "$@"; }
fi
[ -n "$pass" ] && keypath_ok=1 || true
if [ -z "${keypath:-}" ] || [ ! -f "${keypath:-/nonexistent}" ]; then
  if [ -n "${pass:-}" ]; then
    SSH() { sshpass -e ssh "${SSH_OPTS[@]}" "$user@$host" "$@"; }
    SCP() { sshpass -e scp -P "$port" -o StrictHostKeyChecking=accept-new "$@"; }
  fi
fi

echo "== 1. 打源码包（git archive，只含已提交内容）"
cd "$(dirname "$0")/.."
ZIP="$(mktemp -d)/ocrsnip-src.zip"
git archive --format=zip -o "$ZIP" HEAD
echo "   $(du -h "$ZIP" | cut -f1)  $ZIP"

echo "== 2. 传到 $user@$host"
SCP "$ZIP" "ocrsnip-src.zip"

echo "== 3. 远程解压并执行：$ACTION"
case "$ACTION" in
  build)
    SSH "powershell -NoProfile -Command \"Expand-Archive -Force ocrsnip-src.zip \$env:TEMP\\ocrsnip-src; cd \$env:TEMP\\ocrsnip-src; & windows\\build.bat\""
    ;;
  install)
    SSH "powershell -NoProfile -Command \"Expand-Archive -Force ocrsnip-src.zip \$env:TEMP\\ocrsnip-src; cd \$env:TEMP\\ocrsnip-src; & windows\\install.bat\""
    ;;
  selftest)
    SSH "powershell -NoProfile -Command \"cd \$env:TEMP\\ocrsnip-src; python -m pytest -q; python -m ocrsnip selftest --ui qt\""
    ;;
  *) echo "未知动作: $ACTION"; exit 2 ;;
esac

echo "完成。回传产物（在 Linux 上执行）："
echo "  scp -P $port $user@$host:%TEMP%/ocrsnip-src/windows/Output/*.exe ./"
