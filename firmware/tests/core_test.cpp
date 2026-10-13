#include "pikoo_core.hpp"
#include <cassert>
#include <iostream>
int main() {
  using namespace pikoo;
  int16_t samples[480] = {};
  Playback p(1000);
  Playback::Chunk c;
  assert(p.append("a", samples, 480));
  p.done("tool-no-audio");
  assert(p.completed().empty());
  p.done("a");
  assert(p.completed().empty());
  assert(p.take(c));
  assert(p.started(c));
  assert(!p.started(c));
  assert(p.completed().empty());
  p.drained(c);
  assert(p.completed() == std::vector<std::string>{"a"});
  assert(!p.append("a", samples, 480));
  assert(p.append("b", samples, 480));
  assert(p.take(c));
  auto old = c.epoch;
  assert(p.cancel() == std::vector<std::string>{"b"});
  assert(p.epoch() != old);
  assert(!p.append("b", samples, 480));
  p.drained(c);
  assert(p.completed().empty());
  assert(p.append("c", samples, 480));
  assert(p.append("c", samples, 480));
  assert(!p.append("d", samples, 480));
  p.reset();
  assert(!p.busy());
  assert(p.queued() == 0);
  p.announce("announced-before-audio");
  p.cancel();
  assert(!p.append("announced-before-audio",samples,480));
  p.reset();
  Session s;
  assert(!s.upload());
  s.wake(0);
  assert(!s.upload());
  s.voice_ready(1);
  assert(s.upload());
  assert(!s.idle_due(30000, false));
  assert(s.idle_due(30001, false));
  assert(!s.idle_due(40000, true));
  s.mute();
  s.voice_ready(2);
  s.wake(3);
  assert(!s.upload());
  s.stop();
  assert(!s.upload());
  std::vector<int16_t> tone(24000);
  for (size_t i = 0; i < tone.size(); ++i)
    tone[i] = 12000 * std::sin(2 * M_PI * 1000 * i / 24000);
  Resampler whole, parts;
  auto expected = whole.process(tone.data(), tone.size());
  std::vector<int16_t> got;
  for (size_t i = 0; i < tone.size(); i += 137) {
    auto o =
        parts.process(tone.data() + i, std::min<size_t>(137, tone.size() - i));
    got.insert(got.end(), o.begin(), o.end());
  }
  assert(got == expected);
  assert(got.size() == 16000);
  int crosses = 0;
  for (size_t i = 101; i < got.size(); ++i)
    if (got[i - 1] < 0 && got[i] >= 0)
      ++crosses;
  assert(crosses >= 991 && crosses <= 995);
  // Late completion from a disconnected connection cannot complete new
  // playback.
  p.append("old", samples, 480);
  p.take(c);
  p.reset();
  p.append("new", samples, 480);
  p.drained(c);
  p.done("new");
  assert(p.completed().empty());
  std::cout << "PASS: playback drain, cancellation, stale frames, queue "
               "bounds, privacy gate, idle timer, streaming resampler\n";
}
