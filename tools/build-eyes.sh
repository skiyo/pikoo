#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p firmware/build-host
"${CXX:-c++}" -std=c++17 -O2 -Wall -Wextra -Werror \
  -Ifirmware/components/pikoo_eyes/include \
  firmware/components/pikoo_eyes/eyes.cpp firmware/components/pikoo_eyes/eyes_fast.cpp firmware/simulator/eyes-host.cpp \
  -o firmware/build-host/pikoo-eyes
