// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "esp_transport.h"
#include <cstdint>
namespace pikoo {
// Bind before starting the client; release only after its task has stopped.
bool bind_frame_writer(esp_transport_handle_t websocket, esp_transport_handle_t tls);
void release_frame_writer();
uint32_t coalesced_frames();
uint32_t frame_write_errors();
}
