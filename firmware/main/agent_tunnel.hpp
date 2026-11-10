// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "esp_transport.h"
#include <cstdint>
#include <string>

namespace pikoo {
esp_transport_handle_t openai_tunnel(const std::string &host, uint16_t port,
                                     const std::string &proxy_basic);
int tunnel_status(esp_transport_handle_t transport);
void abort_tunnel(esp_transport_handle_t transport);
}
