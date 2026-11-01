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
policy="${PIKOO_WAKE_POLICY:-$(dirname "$model")/wake-policy.json}"
policy_args=(-DPIKOO_WAKE_POLICY=)
trial_args=(-DPIKOO_WAKE_ALLOW_TRIAL=OFF)
if [ "${PIKOO_ALLOW_TRIAL_WAKE:-0}" = 1 ]; then trial_args=(-DPIKOO_WAKE_ALLOW_TRIAL=ON); fi
if [ -f "$policy" ]; then
  policy_args=("-DPIKOO_WAKE_POLICY=$policy")
elif [ -n "${PIKOO_WAKE_POLICY:-}" ] || [ "$(basename "$model")" = hi_pikoo.tflite ]; then
  echo 'Hi Pikoo builds require a matching frozen wake-policy.json.' >&2; exit 1
fi
veto_args=(-DPIKOO_WAKE_VETO=OFF)
if [ -n "${PIKOO_WAKE_VETO_PACK:-}" ]; then
  if [ ! -f "$PIKOO_WAKE_VETO_PACK" ]; then echo 'Missing private verifier pack.' >&2; exit 1; fi
  veto_pack="$(cd "$(dirname "$PIKOO_WAKE_VETO_PACK")" && pwd)/$(basename "$PIKOO_WAKE_VETO_PACK")"
  veto_args=(-DPIKOO_WAKE_VETO=ON "-DPIKOO_WAKE_VETO_MODELS=$veto_pack" "-DPIKOO_WAKE_VETO_CUTOFF=${PIKOO_WAKE_VETO_CUTOFF:-0.5}")
fi
cd "$root/firmware"
idf.py -B build-dualeye -DSDKCONFIG="$PWD/build-dualeye/sdkconfig" -DPIKOO_WAKE_MODEL="$model" -DPIKOO_WAKE_MAX_BYTES="${PIKOO_WAKE_MAX_BYTES:-524288}" -DPIKOO_AUDIO_CAPTURE_BENCHMARK=OFF -DPIKOO_WAKE_BENCHMARK=OFF -DPIKOO_COMMAND_BENCHMARK=OFF "${veto_args[@]}" "${policy_args[@]}" "${trial_args[@]}" build
