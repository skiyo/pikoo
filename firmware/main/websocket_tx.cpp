// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "websocket_tx.hpp"
#include "pikoo_websocket_frame.hpp"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_transport_ws.h"
#include <algorithm>
#include <atomic>

namespace {
constexpr std::size_t PayloadLimit = 8192;
esp_transport_handle_t bound_ws, bound_tls;
uint8_t *buffer;
std::atomic<uint32_t> frames{0}, errors{0};
}
namespace pikoo {
bool bind_frame_writer(esp_transport_handle_t websocket, esp_transport_handle_t tls) {
  if (bound_ws || buffer || !websocket || !tls) return false;
  buffer = static_cast<uint8_t *>(heap_caps_malloc(PayloadLimit + 8, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!buffer) return false;
  bound_tls = tls;
  bound_ws = websocket;
  return true;
}
void release_frame_writer() {
  bound_ws = bound_tls = nullptr;
  heap_caps_free(buffer);
  buffer = nullptr;
}
uint32_t coalesced_frames() { return frames.load(); }
uint32_t frame_write_errors() { return errors.load(); }
}

extern "C" int __real_esp_transport_ws_send_raw(esp_transport_handle_t, ws_transport_opcodes_t,
                                                const char *, int, int);
// ESP WebSocket client holds its TX lock for this call, including PING/PONG.
// Coalesce just Pikoo's client frames; SDK receive/handshake logic stays intact.
// Do not call get_payload_transport_handle(): in IDF 5.5 it resets RX state.
extern "C" int __wrap_esp_transport_ws_send_raw(esp_transport_handle_t transport,
                                               ws_transport_opcodes_t opcode,
                                               const char *data, int size, int timeout_ms) {
  if (transport != bound_ws || !bound_tls || !buffer)
    return __real_esp_transport_ws_send_raw(transport, opcode, data, size, timeout_ms);
  if (size < 0 || std::size_t(size) > PayloadLimit) { ++errors; return -1; }
  uint8_t mask[4];
  esp_fill_random(mask, sizeof(mask));
  const auto total = pikoo::client_frame(uint8_t(opcode), reinterpret_cast<const uint8_t *>(data),
                                        size, mask, buffer, PayloadLimit + 8);
  if (!total) { ++errors; return -1; }
  const int64_t deadline = timeout_ms < 0 ? INT64_MAX : esp_timer_get_time() + int64_t(timeout_ms) * 1000;
  std::size_t offset = 0;
  while (offset < total) {
    const auto remaining = deadline - esp_timer_get_time();
    if (remaining <= 0) { ++errors; return -1; }
    const auto wait = timeout_ms < 0 ? -1 : int(std::min<int64_t>(INT32_MAX, (remaining + 999) / 1000));
    const int written = esp_transport_write(bound_tls, reinterpret_cast<const char *>(buffer + offset),
                                            total - offset, wait);
    // A partial frame must fail the connection, never replay its header.
    if (written <= 0 || std::size_t(written) > total - offset) { ++errors; return -1; }
    offset += written;
  }
  ++frames;
  return size;
}
