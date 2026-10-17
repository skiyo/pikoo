#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
model="${1:-${PIKOO_WAKE_MODEL:-}}"
if [ -z "$model" ] || [ ! -f "$model" ]; then
  echo 'Provide an absolute path to an authorized wake model: tools/build-device.sh /private/model.tflite' >&2
  exit 1
fi
if [ -z "${IDF_PATH:-}" ]; then echo 'Activate ESP-IDF 5.5.5 first.' >&2; exit 1; fi
case "$(idf.py --version)" in
  'ESP-IDF v5.5.5'*) ;;
  *) echo 'This board baseline requires ESP-IDF 5.5.5.' >&2; exit 1 ;;
esac
model="$(cd "$(dirname "$model")" && pwd)/$(basename "$model")"
cd "$root/firmware"
idf.py -B build-dualeye -DSDKCONFIG="$PWD/build-dualeye/sdkconfig" -DPIKOO_WAKE_MODEL="$model" build
