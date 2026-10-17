#pragma once
#include <cstdint>
namespace pikoo {
// ES7210 datasheet Fig. 2e: TDM I2S wire order is ADC1, ADC3,
// ADC2, ADC4. Reading two 32-bit I2S slots preserves each 16-bit pair.
inline void es7210_mr(int32_t left_slot,int16_t &mic,int16_t &reference) {
  mic=static_cast<int16_t>(uint32_t(left_slot)>>16);
  reference=static_cast<int16_t>(uint32_t(left_slot)&0xffffu);
}
// The ES8311 reads 16 significant bits from each 32-clock stereo slot.
inline int32_t dac_slot(int16_t sample){return int32_t(sample)*65536;}
}
