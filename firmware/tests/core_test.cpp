#include "pikoo_core.hpp"
#include "pikoo_button.hpp"
#include "pikoo_audio_slots.hpp"
#include <cassert>
#include <iostream>
int main() {
  using namespace pikoo;
  int16_t mapped_mic=0,mapped_ref=0;
  es7210_mr(int32_t(0x80017fffu),mapped_mic,mapped_ref);
  assert(mapped_mic==-32767&&mapped_ref==32767);
  es7210_mr(int32_t(0x7fff8000u),mapped_mic,mapped_ref);
  assert(mapped_mic==32767&&mapped_ref==-32768);
  assert(dac_slot(-32768)==INT32_MIN&&dac_slot(32767)==int32_t(0x7fff0000));
  // A continuously replenished microphone stream cannot starve incoming audio
  // or cancellation handling, even when the producer is faster than the link.
  unsigned sent=0;
  assert(pump_bounded(2,[]{return true;},[&]{++sent;})==2);
  assert(sent==2);
  // Mechanical bounce cannot wake twice; a press need not wait for double-click.
  Button button;
  assert(button.update(true,0)==Button::None);
  assert(button.update(false,5)==Button::None);
  assert(button.update(true,10)==Button::None);
  assert(button.update(true,35)==Button::Press);
  assert(button.update(false,80)==Button::None);
  assert(button.update(false,105)==Button::None);
  assert(button.update(true,140)==Button::None);
  assert(button.update(true,165)==Button::Double);
  assert(button.update(true,2164)==Button::None);
  assert(button.update(true,2165)==Button::Hold);
  assert(button.update(true,3000)==Button::None);
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
  // Independent dense convolution checks both polyphase branches, including
  // ring-buffer wraparound and zero insertion, on a broadband input.
  std::array<double,63> kernel{};
  double weight=0;
  for(int k=0;k<63;k++) {
    double x=k-31,fc=.15;
    kernel[k]=(x==0?2*fc:std::sin(2*M_PI*fc*x)/(M_PI*x))*
      (.42-.5*std::cos(2*M_PI*k/62)+.08*std::cos(4*M_PI*k/62));
    weight+=kernel[k];
  }
  for(auto &v:kernel)v*=2/weight;
  std::vector<int16_t> broadband(2048);uint32_t seed=37;
  for(auto &v:broadband){seed=1664525u*seed+1013904223u;v=int(seed>>16)-32768;}
  Resampler polyphase;
  auto filtered=polyphase.process(broadband.data(),broadband.size());
  for(size_t i=0;i<filtered.size();i++) {
    double value=0;int pos=int(i*3);
    for(int k=0;k<63&&k<=pos;k++)if((pos-k)%2==0)value+=kernel[k]*broadband[(pos-k)/2];
    auto dense=int(std::clamp(value,-32768.,32767.));
    assert(std::abs(int(filtered[i])-dense)<=2);
  }
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
