#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash tools/build-eyes.sh
"${CXX:-c++}" -std=c++17 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Ifirmware/components/pikoo_eyes/include firmware/components/pikoo_eyes/eyes.cpp \
  firmware/simulator/eyes-core.test.cpp -o firmware/build-host/test-eyes
ASAN_OPTIONS=detect_leaks=0 firmware/build-host/test-eyes
"${CXX:-c++}" -std=c++17 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -DPIKOO_EYES_FAST_TEST -Ifirmware/components/pikoo_eyes/include \
  firmware/components/pikoo_eyes/eyes.cpp firmware/components/pikoo_eyes/eyes_fast.cpp \
  firmware/simulator/eyes-core.test.cpp -o firmware/build-host/test-eyes-fast
ASAN_OPTIONS=detect_leaks=0 firmware/build-host/test-eyes-fast
