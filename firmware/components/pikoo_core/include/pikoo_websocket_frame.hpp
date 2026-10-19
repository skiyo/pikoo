// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include <cstddef>
#include <cstdint>

namespace pikoo {
// RFC 6455 client frame. Caller supplies fresh random mask bytes and storage.
// Keep the payload unchanged: callers may retry or release their own buffer.
inline std::size_t client_frame(uint8_t opcode, const uint8_t *payload,
                                std::size_t size, const uint8_t mask[4],
                                uint8_t *out, std::size_t capacity) {
  const auto kind = opcode & 15;
  if (!out || !mask || (size && !payload) || size > 65535 ||
      (opcode & 0x70) || (kind != 0 && kind != 1 && kind != 2 &&
                         kind != 8 && kind != 9 && kind != 10) ||
      (kind >= 8 && (!(opcode & 0x80) || size > 125)))
    return 0;
  const std::size_t header = size < 126 ? 6 : 8;
  if (capacity < header + size) return 0;
  out[0] = opcode;
  std::size_t offset = 2;
  out[1] = 0x80 | (size < 126 ? uint8_t(size) : 126);
  if (size >= 126) {
    out[offset++] = uint8_t(size >> 8);
    out[offset++] = uint8_t(size);
  }
  for (int i = 0; i < 4; ++i) out[offset++] = mask[i];
  for (std::size_t i = 0; i < size; ++i) out[offset + i] = payload[i] ^ mask[i % 4];
  return header + size;
}
} // namespace pikoo
