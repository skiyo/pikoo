#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
workspace="$(cd "$repo/../.." && pwd)"
cd "$repo"
node_bin="${PIKOO_NODE:-$workspace/work/node24/node_modules/node/bin/node}"
if [ ! -x "$node_bin" ]; then node_bin="$(command -v node || true)"; fi
if [ -z "$node_bin" ]; then echo '缺少 Node.js，请安装 Node.js 24 LTS。'; exit 1; fi
if [ "$("$node_bin" -p 'Number(process.versions.node.split(".")[0])')" -lt 24 ]; then echo '需要 Node.js 24 或更新版本。'; exit 1; fi
if ! command -v "${CXX:-c++}" >/dev/null; then echo '缺少 C++ 编译器，请安装 Xcode Command Line Tools。'; exit 1; fi
if [ ! -d server/node_modules/ws ]; then echo '缺少本机服务依赖，请先在 server 目录执行 npm ci。'; exit 1; fi
export PIKOO_SIM_PORT="${PIKOO_SIM_PORT:-8793}"
if [ "${PIKOO_SIM_MOCK:-0}" = 1 ]; then
  unset PIKOO_SIM_CONFIG
else
  export PIKOO_SIM_CONFIG="${PIKOO_SIM_CONFIG:-$workspace/work/private/simulator.json}"
  if [ ! -f "$PIKOO_SIM_CONFIG" ]; then echo '未找到私密服务器配置。可设置 PIKOO_SIM_CONFIG，或用 PIKOO_SIM_MOCK=1 启动离线模拟。'; exit 1; fi
fi
export PIKOO_WAKE_PYTHON="${PIKOO_WAKE_PYTHON:-$workspace/work/training-env/bin/python}"
export PIKOO_WAKE_MODEL="${PIKOO_WAKE_MODEL:-$workspace/outputs/Pikoo_唤醒模型_V5/nihao_pikoo.tflite}"
export PIKOO_WAKE_LABEL="${PIKOO_WAKE_LABEL:-你好皮酷 V5（本机受限模型）}"
if [ "${PIKOO_SIM_MOCK:-0}" = 1 ]; then unset PIKOO_WAKE_PYTHON; else
  if [ ! -x "$PIKOO_WAKE_PYTHON" ] || [ ! -f "$PIKOO_WAKE_MODEL" ]; then echo '缺少本地唤醒运行环境或 V5 模型，请检查 PIKOO_WAKE_PYTHON 和 PIKOO_WAKE_MODEL。'; exit 1; fi
  if ! "$PIKOO_WAKE_PYTHON" -c 'import tensorflow, pymicro_features' >/dev/null 2>&1; then echo '唤醒运行环境缺少 TensorFlow 或 pymicro_features。'; exit 1; fi
fi
bash tools/build-eyes.sh
exec "$node_bin" tools/dualeye-launcher.mjs start
