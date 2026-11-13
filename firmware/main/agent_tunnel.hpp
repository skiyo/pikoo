// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "esp_transport.h"
#include "pikoo_config.hpp"
namespace pikoo {
// Verified TLS to the requested endpoint, optionally inside HTTPS CONNECT.
esp_transport_handle_t service_transport(const NetworkConfig &network);
int tunnel_status(esp_transport_handle_t transport);
void abort_tunnel(esp_transport_handle_t transport);
}
