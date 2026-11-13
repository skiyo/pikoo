#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
node_bin="${PIKOO_NODE:-$(command -v node || true)}"
python_bin="${PIKOO_CHECK_PYTHON:-python3}"
if [ ! -x "$node_bin" ] || [ "$("$node_bin" -p 'Number(process.versions.node.split(".")[0])')" -lt 24 ]; then
  echo 'Checks require Node.js 24 or newer.'; exit 1
fi
if [ ! -d firmware/simulator/node_modules/ws ]; then
  echo 'Install dependencies first: (cd firmware/simulator && npm ci --ignore-scripts)'; exit 1
fi
echo 'Checking native audio/session core and eyes'
bash tools/test-core.sh
bash tools/test-eyes.sh
echo 'Checking the offline eye preview'
"$node_bin" --test firmware/simulator/*.test.mjs
"$node_bin" --test training/hi_pikoo_generate.test.cjs training/wake_mixed_test_generate.test.cjs
PIKOO_SANITIZE=1 bash tools/test-local-agent.sh --services
echo 'Checking Python tooling and training units (optional runtime tests may skip)'
"$python_bin" -m unittest discover -s tools -p 'test_*.py'
if [[ "${PIKOO_CHECK_TRAINING:-0}" == 1 ]]; then
  "$python_bin" -m unittest discover -s training -p 'test_*.py'
else
  echo 'Optional Python training suite skipped; set PIKOO_CHECK_TRAINING=1 with training/requirements.txt installed.'
fi
echo 'Software checks completed. This is not hardware or live-provider acceptance.'
