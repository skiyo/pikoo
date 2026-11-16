#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IDF_PATH:?Set IDF_PATH for cJSON}"
json="${CJSON_SRC_DIR:-$IDF_PATH/components/json/cJSON}"
out="$(mktemp -d "${TMPDIR:-/tmp}/pikoo-body-test.XXXXXXXX")"
trap 'rm -rf "$out"' EXIT
opts=(-O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined)
cc "${opts[@]}" -Wno-deprecated-declarations -I"$json" -c "$json/cJSON.c" -o "$out/json.o"
c++ -std=c++17 "${opts[@]}" -I"$json" -Ifirmware/components/pikoo_core/include -Ifirmware/components/pikoo_eyes/include \
 firmware/tests/body_test.cpp firmware/components/pikoo_core/pikoo_agent.cpp firmware/components/pikoo_core/pikoo_config.cpp firmware/components/pikoo_core/pikoo_backend.cpp firmware/components/pikoo_core/pikoo_http.cpp "$out/json.o" -o "$out/test-body"
"$out/test-body"
