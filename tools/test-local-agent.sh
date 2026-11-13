#!/usr/bin/env bash
# Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IDF_PATH:?Set IDF_PATH to the ESP-IDF 5.5 checkout for cJSON}"
json="${CJSON_SRC_DIR:-$IDF_PATH/components/json/cJSON}"
if [[ ! -f "$json/cJSON.c" ]]; then
  echo "Set CJSON_SRC_DIR to a directory containing cJSON.c and cJSON.h" >&2
  exit 1
fi
out="$(mktemp -d "${TMPDIR:-/tmp}/pikoo-agent-test.XXXXXXXX")"
trap 'rm -rf "$out"' EXIT
crypto=()
if [[ -n "${OPENSSL_PREFIX:-}" ]]; then
  crypto=(-I"$OPENSSL_PREFIX/include" -L"$OPENSSL_PREFIX/lib" -Wl,-rpath,"$OPENSSL_PREFIX/lib")
fi
opts=(-O2 -Wall -Wextra -Werror)
if [[ "${PIKOO_SANITIZE:-0}" == 1 ]]; then
  opts+=(-fsanitize=address,undefined -g)
fi
"${CC:-cc}" "${opts[@]}" -Wno-deprecated-declarations -I"$json" -c "$json/cJSON.c" -o "$out/cJSON.o"
"${CXX:-c++}" -std=c++17 "${opts[@]}" -I"$json" \
  -Ifirmware/components/pikoo_core/include -Ifirmware/components/pikoo_eyes/include \
  firmware/simulator/local-agent.cpp firmware/components/pikoo_core/pikoo_agent.cpp firmware/components/pikoo_core/pikoo_config.cpp \
  firmware/components/pikoo_core/pikoo_backend.cpp firmware/components/pikoo_core/pikoo_http.cpp \
  firmware/components/pikoo_eyes/eyes.cpp firmware/components/pikoo_eyes/eyes_fast.cpp \
  "$out/cJSON.o" "${crypto[@]}" -lcrypto -o "$out/local-agent"
if [[ "${1:-}" == --services || "${1:-}" == --network ]]; then
  mode="$1"; shift
  "$out/local-agent" 0
  "${CXX:-c++}" -std=c++17 "${opts[@]}" -I"$json" -Ifirmware/components/pikoo_core/include \
    firmware/simulator/services-host.cpp firmware/components/pikoo_core/pikoo_agent.cpp \
    firmware/components/pikoo_core/pikoo_config.cpp firmware/components/pikoo_core/pikoo_backend.cpp \
    firmware/components/pikoo_core/pikoo_http.cpp "$out/cJSON.o" -o "$out/services-host"
  if [[ "$mode" == --network ]]; then python3 tools/test-local-agent-network.py "$out/services-host" "$@"
  else python3 tools/test-agent-services.py "$out/services-host" "$@"; fi
else
  "$out/local-agent" "$@"
fi
