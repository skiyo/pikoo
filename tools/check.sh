#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
node_bin="${PIKOO_NODE:-$(command -v node || true)}"
python_bin="${PIKOO_CHECK_PYTHON:-python3}"
if [ ! -x "$node_bin" ] || [ "$("$node_bin" -p 'Number(process.versions.node.split(".")[0])')" -lt 24 ]; then
  echo 'Checks require Node.js 24 or newer.'; exit 1
fi
if [ ! -d server/node_modules/ws ]; then
  echo 'Install dependencies first: (cd server && npm ci --ignore-scripts)'; exit 1
fi
echo 'Checking native audio/session core and eyes'
bash tools/test-core.sh
bash tools/test-eyes.sh
echo 'Checking simulator and server'
"$node_bin" --test firmware/simulator/*.test.mjs
(cd server && "$node_bin" --test *.test.mjs)
echo 'Checking Python tooling and training units (optional runtime tests may skip)'
"$python_bin" -m unittest discover -s tools -p 'test_*.py'
"$python_bin" -m unittest discover -s training -p 'test_*.py'
echo 'Software checks completed. This is not hardware or live-provider acceptance.'
