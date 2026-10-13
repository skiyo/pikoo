#pragma once
#include <cstddef>
#include <cstdint>
bool wake_init();
bool wake_feed(const int16_t *pcm, size_t count);
void wake_reset();
