#include "pikoo_core.hpp"
#include "pikoo_button.hpp"
#include "pikoo_audio_slots.hpp"
#include "pikoo_interaction.hpp"
#include "pikoo_volume.hpp"
#include "pikoo_continuous.hpp"
#include "eye_state.hpp"
#include <cassert>
#include <iostream>
int main() {
  using namespace pikoo;
  ContinuousStream stream;
  stream.ready("s1",3);assert(stream.accept("s1",3,0));assert(!stream.accept("s1",3,0));
  assert(!stream.accept("s1",3,2));assert(stream.accept("s1",3,1));
  stream.clear(4);assert(!stream.accept("s1",3,2));stream.ready("s2",5);
  assert(!stream.accept("s1",5,0));assert(stream.accept("s2",5,0));
  int db=123;
  for(int level=-50;level<=0;++level){
    assert(volume_command(("volume "+std::to_string(level)).c_str(),db));
    assert(db==level);
  }
  for(auto command:{"volume -51","volume 1","volume -2junk","volume -2.0","volume ","volume  -2","volume +0","volume -99999999999999999","wake -2"}){
    db=123;assert(!volume_command(command,db));assert(db==123);
  }
  Interaction flow;
  flow.wake();assert(flow.greeting_pending());flow.greeting_sent();
  // Transport reconnects and provider rebuilds never call wake().
  assert(!flow.greeting_pending());
  for(auto text:{"再见！","皮酷，再见。","拜拜","好了，再见","晚安皮酷","Pikoo，再见。","再见 Pikoo","Goodbye, Pikoo!"})assert(is_farewell(text));
  for(auto text:{"不要说再见","再见是什么意思","你会说再见吗","故事里他说再见","再见之后呢","你好皮酷"})assert(!is_farewell(text));
  assert(!flow.transcript("assistant",true,"再见","t",0));
  assert(!flow.transcript("user",false,"再见","t",0));
  flow.response("old","old-response");flow.drained("old-response");
  assert(flow.transcript("user",true,"再见","bye-turn",100));
  assert(flow.closing()&&!flow.finish_due(200,false));
  flow.drained("old-response");assert(!flow.finish_due(200,false));
  flow.response("bye-turn","bye-response");
  flow.drained("bye-response");assert(!flow.finish_due(200,true));
  assert(flow.finish_due(200,false));
  flow.reset();assert(!flow.closing()&&!flow.greeting_pending());
  flow.wake();flow.response("fast","fast-response");flow.drained("fast-response");
  assert(flow.transcript("user",true,"拜拜","fast",100));assert(flow.finish_due(101,false));
  flow.reset();flow.transcript("user",true,"再见","timeout",100);
  assert(!flow.finish_due(20099,false));assert(flow.finish_due(20100,true));
  assert(eye_state(Session::State::Speaking)==eyes::State::Speaking);
  assert(eye_state(Session::State::Thinking)==eyes::State::Thinking);
  assert(eye_state(Session::State::Connecting)==eyes::State::Connecting);
  using namespace pikoo;
  int16_t mapped_mic=0,mapped_ref=0;
  es7210_mr(int32_t(0x80017fffu),mapped_mic,mapped_ref);
  assert(mapped_mic==-32767&&mapped_ref==32767);
  es7210_mr(int32_t(0x7fff8000u),mapped_mic,mapped_ref);
  assert(mapped_mic==32767&&mapped_ref==-32768);
  assert(dac_slot(-32768)==INT32_MIN&&dac_slot(32767)==int32_t(0x7fff0000));
  // Start with 120 ms of speech queued, but do not wait forever for a short
  // answer or a stalled upstream. Cancellation must discard a waiting start.
  {
    int16_t block[1440]{};Playback buffered;Playback::Chunk first;
    assert(buffered.append("buffer",block,1440));
    assert(!buffered.take(first,2880,0));
    assert(!buffered.take(first,2880,199));
    assert(buffered.append("buffer",block,1440));
    assert(buffered.take(first,2880,199));assert(buffered.started(first));
    assert(buffered.take(first,2880,199));
    buffered.reset();assert(buffered.append("short",block,100));
    assert(!buffered.take(first,2880,300));buffered.done("short");
    assert(buffered.take(first,2880,301));
    buffered.reset();assert(buffered.append("stalled",block,240));
    assert(!buffered.take(first,2880,500));assert(buffered.take(first,2880,700));
    buffered.reset();assert(buffered.append("cancelled",block,100));
    assert(!buffered.take(first,2880,800));buffered.cancel();
    assert(!buffered.take(first,2880,1000));
    assert(buffered.append("new",block,100));assert(!buffered.take(first,2880,1000));
    // Reproduce a second turn: a single-sample prefix arrives 315 ms before
    // the real PCM. It must not start the speaker and create an audible gap.
    buffered.reset();assert(buffered.append("prefix",block,1));
    assert(!buffered.take(first,2880,0));
    assert(!buffered.take(first,2880,200));
    assert(!buffered.take(first,2880,314));
    assert(buffered.append("prefix",block,1440));
    assert(buffered.append("prefix",block,1440));
    assert(buffered.take(first,2880,315));assert(first.pcm.size()==1);
    assert(buffered.started(first));
    assert(buffered.take(first,2880,315));assert(first.pcm.size()==1440);
  }
  {
    // Device trace: 140 ms arrives first, the next 320 ms arrives 520 ms later.
    // A 120 ms start underruns. The bounded jitter prefill retains every sample.
    Playback jitter;Playback::Chunk part;int16_t a[3360]{},b[7680]{};
    assert(jitter.append("jitter",a,3360));
    assert(!jitter.take(part,12000,0,600));
    assert(!jitter.take(part,12000,200,600));
    assert(jitter.append("jitter",b,7680));
    assert(!jitter.take(part,12000,520,600));
    assert(jitter.take(part,12000,600,600));assert(jitter.started(part));
    assert(part.pcm.size()==3360);assert(jitter.take(part,12000,600,600));
    assert(part.pcm.size()==7680);jitter.cancel();
    assert(!jitter.take(part,12000,601,600));
  }
  // A continuously replenished microphone stream cannot starve incoming audio
  {
    Playback live;Playback::Chunk chunk;int16_t pcm[480]{};
    assert(live.append("stream",pcm,480));
    assert(!live.take(chunk,960,0,1500,true));
    assert(live.append("stream",pcm,480));
    assert(live.take(chunk,960,10,1500,true));assert(live.started(chunk));
    live.drained(chunk);assert(live.take(chunk,960,20,1500,true));live.drained(chunk);
    assert(live.in_flight()==0);assert(!live.take(chunk,960,30,1500,true));
    // The same continuous stream buffers again after starvation; no fake done.
    assert(live.completed().empty());assert(live.append("stream",pcm,480));
    assert(!live.take(chunk,960,40,1500,true));
    assert(live.append("stream",pcm,480));assert(live.take(chunk,960,50,1500,true));
    live.cancel();assert(!live.take(chunk,960,60,1500,true));
  }
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
  assert(!s.idle_due(3600000, false, true));
  assert(s.idle_due(3600000, false, false));
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
