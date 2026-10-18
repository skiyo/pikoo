#pragma once
#include <cstddef>
#include <cstdint>
bool wake_verifier_init();
void wake_verifier_invalidate();
void wake_verifier_reset();
bool wake_verifier_feed(const int16_t *pcm,size_t count,uint32_t epoch);
uint32_t wake_verifier_candidates();
uint32_t wake_verifier_rejected();
uint32_t wake_verifier_cancelled();
uint32_t wake_verifier_errors();
uint32_t wake_verifier_last_us();
