#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"
node_bin="${PIKOO_NODE:-}"
if [ ! -x "$node_bin" ]; then node_bin="$(command -v node || true)"; fi
if [ -z "$node_bin" ]; then echo '缺少 Node.js，无法读取本机运行记录。'; exit 1; fi
exec "$node_bin" tools/dualeye-launcher.mjs stop
