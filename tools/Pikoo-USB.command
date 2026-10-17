#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
idf_dir="${PIKOO_IDF_PATH:-${IDF_PATH:-}}"
workspace="$(cd "$root/../.." && pwd)"
if [ -z "$idf_dir" ] && [ -f "$workspace/work/esp-idf/export.sh" ]; then
  idf_dir="$workspace/work/esp-idf"
  export IDF_TOOLS_PATH="$workspace/work/idf-tools"
  for candidate in "$IDF_TOOLS_PATH"/python_env/idf5.5_py3.11_env/bin; do
    if [ -x "$candidate/python" ]; then export PATH="$candidate:$PATH"; fi
  done
fi
if [ -z "$idf_dir" ]; then idf_dir="$HOME/esp/esp-idf"; fi
if [ ! -f "$idf_dir/export.sh" ]; then
  echo '找不到 ESP-IDF 5.5.5。请安装后设置 PIKOO_IDF_PATH，详见 docs/firmware.md。'
  read -r -p '按回车关闭'; exit 1
fi
source "$idf_dir/export.sh"
python "$root/tools/usb-setup.py"
read -r -p '按回车关闭'
