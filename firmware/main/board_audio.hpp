#pragma once
#include "esp_err.h"
#include <atomic>
#include <cstddef>
#include <cstdint>
namespace board {
esp_err_t audio_init();
// Interleaved physical microphone / DAC reference, two 16-bit channels.
bool capture(int16_t *mr, size_t frames);
void capture_enabled(bool enabled);
void playback_idle();
float microphone_level();
float reference_level();
float microphone_peak();
float reference_peak();
float output_level();
uint32_t capture_errors();
uint32_t playback_errors();
esp_err_t set_volume(int db);
bool play(const int16_t *mono, size_t samples, uint32_t epoch);
void silence();
uint32_t generation();
void drain();
} // namespace board
