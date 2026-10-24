#pragma once
#include <charconv>
#include <cstring>

namespace pikoo {
// Exact integer dB commands, bounded by the codec's safe attenuation range.
inline bool volume_command(const char *command, int &db) {
  if (std::strncmp(command, "volume ", 7) != 0) return false;
  const char *first = command + 7, *last = first + std::strlen(first);
  int parsed = 0;
  auto result = std::from_chars(first, last, parsed);
  if (result.ec != std::errc{} || result.ptr != last || parsed < -50 || parsed > 0)
    return false;
  db = parsed;
  return true;
}
}
