// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <array>
#include <cstddef>

namespace pikoo {
template <std::size_t N> class WakeDecision {
  static_assert(N == 3 || N == 5, "Only qualified 3/5-step policies supported");
  std::array<float, N> values_{};
  std::size_t next_ = 0, count_ = 0;
  float score_ = 0;
public:
  void reset() { values_.fill(0); next_ = count_ = 0; score_ = 0; }
  float score() const { return score_; }
  bool feed(float value, float threshold) {
    values_[next_] = value;
    next_ = (next_ + 1) % N;
    if (count_ < N) ++count_;
    if (count_ < N) { score_ = 0; return false; }
    float sum = 0;
    for (float p : values_) sum += p;
    score_ = sum / static_cast<float>(N);
    return score_ >= threshold;
  }
};
}
