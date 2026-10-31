// SPDX-License-Identifier: Apache-2.0
#include "pikoo/wake_decision.hpp"
#include <cassert>
#include <cmath>
int main() {
  pikoo::WakeDecision<3> short_policy;
  assert(!short_policy.feed(1, .9f));
  assert(!short_policy.feed(1, .9f));
  assert(short_policy.feed(1, .9f));
  short_policy.reset();
  assert(!short_policy.feed(0, .9f));
  assert(short_policy.score() == 0);
  pikoo::WakeDecision<5> legacy;
  float ring[5]{};
  for (unsigned i = 0; i < 1000; ++i) {
    const float p = static_cast<float>((i * 37) % 256) / 255;
    ring[i % 5] = p;
    float expected = 0;
    for (float value : ring) expected += value;
    expected = i >= 4 ? expected / 5 : 0;
    bool hit = legacy.feed(p, .9f);
    assert(legacy.score() == expected);
    assert(hit == (i >= 4 && expected >= .9f));
  }
}
