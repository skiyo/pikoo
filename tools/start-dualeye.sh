#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"
node_bin="${PIKOO_NODE:-}"
if [ ! -x "$node_bin" ]; then node_bin="$(command -v node || true)"; fi
if [ -z "$node_bin" ]; then echo '缺少 Node.js，请安装 Node.js 24 LTS。'; exit 1; fi
if [ "$("$node_bin" -p 'Number(process.versions.node.split(".")[0])')" -lt 24 ]; then echo '需要 Node.js 24 或更新版本。'; exit 1; fi
if ! command -v "${CXX:-c++}" >/dev/null; then echo '缺少 C++ 编译器，请安装 Xcode Command Line Tools。'; exit 1; fi
if [ ! -d firmware/simulator/node_modules/ws ]; then echo 'Install simulator dependencies: (cd firmware/simulator && npm ci --ignore-scripts)'; exit 1; fi
export PIKOO_SIM_PORT="${PIKOO_SIM_PORT:-8793}"
bash tools/build-eyes.sh
exec "$node_bin" tools/dualeye-launcher.mjs start
