// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "pikoo_backend.hpp"
#include <atomic>
namespace pikoo {
HttpResult service_request(const HttpRequest &request,
                           const NetworkConfig &network,
                           const std::atomic<uint64_t> &current,
                           const std::atomic<uint64_t> &scope);
// Called only by the single backend worker. Cancelled/idle connections expire.
void service_request_idle(const std::atomic<uint64_t> &current);
}
