#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"
node_bin="${PIKOO_NODE:-}"
if [ ! -x "$node_bin" ]; then node_bin="$(command -v node || true)"; fi
if [ -z "$node_bin" ]; then echo '缺少 Node.js，请安装 Node.js 24 LTS。'; exit 1; fi
if [ "$("$node_bin" -p 'Number(process.versions.node.split(".")[0])')" -lt 24 ]; then echo '需要 Node.js 24 或更新版本。'; exit 1; fi
if ! command -v "${CXX:-c++}" >/dev/null; then echo '缺少 C++ 编译器，请安装 Xcode Command Line Tools。'; exit 1; fi
if [ ! -d server/node_modules/ws ]; then echo '缺少本机服务依赖，请先在 server 目录执行 npm ci。'; exit 1; fi
export PIKOO_SIM_PORT="${PIKOO_SIM_PORT:-8793}"
if [ "${PIKOO_SIM_MOCK:-0}" = 1 ]; then
  unset PIKOO_SIM_CONFIG
elif [ -n "${PIKOO_SIM_CONFIG:-}" ] && [ ! -f "$PIKOO_SIM_CONFIG" ]; then
  echo 'Server configuration not found. Set PIKOO_SIM_CONFIG to a private file, or unset it for an offline demo.'; exit 1
fi
if [ -n "${PIKOO_WAKE_PYTHON:-}" ] || [ -n "${PIKOO_WAKE_MODEL:-}" ]; then
  if [ ! -x "${PIKOO_WAKE_PYTHON:-}" ] || [ ! -f "${PIKOO_WAKE_MODEL:-}" ]; then echo 'Local wake requires both PIKOO_WAKE_PYTHON (executable) and PIKOO_WAKE_MODEL (private model file).'; exit 1; fi
  if ! "$PIKOO_WAKE_PYTHON" -c 'import tensorflow, pymicro_features' >/dev/null 2>&1; then echo '唤醒运行环境缺少 TensorFlow 或 pymicro_features。'; exit 1; fi
fi
bash tools/build-eyes.sh
exec "$node_bin" tools/dualeye-launcher.mjs start
