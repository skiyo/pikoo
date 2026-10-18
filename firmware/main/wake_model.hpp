#pragma once
#include <cstddef>
#include <cstdint>
bool wake_init();
bool wake_feed(const int16_t *pcm, size_t count,bool count_detection=true);
void wake_reset();
void wake_mark_confirmed();
uint32_t wake_max_inference_us();
uint32_t wake_inference_count();
float wake_score();
float wake_peak_score();
float wake_raw_peak_score();
uint32_t wake_detection_count();
uint32_t wake_error_count();
void wake_trace_start();
void wake_capture_start();
void wake_cancel_diagnostics();
