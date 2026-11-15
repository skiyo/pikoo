#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${IDF_PATH:?Set IDF_PATH for cJSON}"
json="${CJSON_SRC_DIR:-$IDF_PATH/components/json/cJSON}"
mkdir -p firmware/build-host
cc -O2 -Wno-deprecated-declarations -I"$json" -c "$json/cJSON.c" -o firmware/build-host/body-json.o
c++ -std=c++17 -O2 -Wall -Wextra -Werror -I"$json" -Ifirmware/components/pikoo_core/include -Ifirmware/components/pikoo_eyes/include \
 firmware/simulator/body-host.cpp firmware/components/pikoo_core/pikoo_agent.cpp firmware/components/pikoo_core/pikoo_config.cpp firmware/components/pikoo_core/pikoo_backend.cpp firmware/components/pikoo_core/pikoo_http.cpp firmware/components/pikoo_eyes/eyes.cpp firmware/components/pikoo_eyes/eyes_fast.cpp firmware/build-host/body-json.o -o firmware/build-host/body-host
