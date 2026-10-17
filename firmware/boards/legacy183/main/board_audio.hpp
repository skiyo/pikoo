#pragma once
#include "esp_err.h"
#include <atomic>
#include <cstddef>
#include <cstdint>
namespace board {
esp_err_t audio_init();
bool capture(int16_t *four_channels, size_t frames);
bool play(const int16_t *mono, size_t samples, uint32_t epoch);
void silence();
uint32_t generation();
void drain();
} // namespace board
