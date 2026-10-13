#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p firmware/build-host
"${CXX:-c++}" -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -g -Ifirmware/components/pikoo_core/include firmware/tests/core_test.cpp -o firmware/build-host/core-test
firmware/build-host/core-test
