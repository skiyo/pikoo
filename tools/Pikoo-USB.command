#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
idf_dir="${PIKOO_IDF_PATH:-${IDF_PATH:-}}"
if [ -z "$idf_dir" ]; then idf_dir="$HOME/esp/esp-idf"; fi
if [ ! -f "$idf_dir/export.sh" ]; then
  echo 'ESP-IDF 5.5.5 not found. Set PIKOO_IDF_PATH; see docs/firmware.md.'
  read -r -p 'Press Enter to close'; exit 1
fi
source "$idf_dir/export.sh"
python "$root/tools/usb-setup.py" "$@"
read -r -p 'Press Enter to close'
