#include "pikoo_core.hpp"
#include <cassert>
#include <iostream>

namespace {
struct Result { unsigned first_ms=0,starved_ms=0;size_t consumed=0; };
Result replay(size_t prefill,uint64_t max_wait) {
  // NET5 reconnect greeting: packet timestamps relative to the one-sample
  // prefix. Sizes and timing only; no user/provider audio is stored here.
  struct Arrival { unsigned at;size_t samples; };
  const Arrival trace[]={{0,1},{62,2640},{600,12480},{621,2880},
                         {1003,8640},{1932,11520}};
  pikoo::Playback playback; pikoo::Playback::Chunk chunk;
  std::vector<int16_t> silence(12480);
  size_t next=0,position=0;bool active=false,started=false;
  Result result;
  // Stop just after the last known arrival; subsequent packet timing is not
  // in this trace and cannot legitimately be invented as an upstream stall.
  for(unsigned ms=0;ms<=1933;++ms) {
    while(next<6&&trace[next].at==ms) {
      assert(playback.append("reply",silence.data(),trace[next].samples));++next;
    }
    unsigned budget=24; // Independent 24 kHz playback clock, 1 ms steps.
    while(budget) {
      if(!active) {
        if(!playback.take(chunk,prefill,ms,max_wait)) {
          if(started)++result.starved_ms;
          break;
        }
        active=true;position=0;
        if(playback.started(chunk)){started=true;result.first_ms=ms;}
      }
      size_t count=std::min<size_t>(budget,chunk.pcm.size()-position);
      position+=count;budget-=count;result.consumed+=count;
      if(position==chunk.pcm.size()){playback.drained(chunk);active=false;}
    }
  }
  size_t received=0;for(const auto &packet:trace)received+=packet.samples;
  assert(result.consumed+playback.queued()+(active?chunk.pcm.size()-position:0)==received);
  return result;
}
}
int main() {
  const auto previous=replay(12000,600);
  const auto fixed=replay(pikoo::Playback::InitialSamples,pikoo::Playback::MaxInitialWaitMs);
  assert(previous.first_ms==600&&previous.starved_ms>=200);
  assert(fixed.first_ms==1003&&fixed.starved_ms==0);
  // Bounded waiting, immediate completed short replies, and cancel/reset are
  // still required. A reconnect must not release a cancelled prefix or PCM.
  pikoo::Playback p;pikoo::Playback::Chunk c;int16_t pcm[240]{};
  assert(p.append("stalled",pcm,240));
  assert(!p.take(c,pikoo::Playback::InitialSamples,100,pikoo::Playback::MaxInitialWaitMs));
  assert(!p.take(c,pikoo::Playback::InitialSamples,1599,pikoo::Playback::MaxInitialWaitMs));
  assert(p.take(c,pikoo::Playback::InitialSamples,1600,pikoo::Playback::MaxInitialWaitMs));
  p.reset();assert(p.append("short",pcm,20));p.done("short");
  assert(p.take(c,pikoo::Playback::InitialSamples,1700,pikoo::Playback::MaxInitialWaitMs));
  p.reset();assert(p.append("old",pcm,240));
  assert(!p.take(c,pikoo::Playback::InitialSamples,2000,pikoo::Playback::MaxInitialWaitMs));
  p.cancel();assert(!p.append("old",pcm,240));
  assert(!p.take(c,pikoo::Playback::InitialSamples,4000,pikoo::Playback::MaxInitialWaitMs));
  p.reset();assert(p.append("new",pcm,240));
  assert(!p.take(c,pikoo::Playback::InitialSamples,4000,pikoo::Playback::MaxInitialWaitMs));
  pikoo::Playback bounded(240);
  assert(!bounded.append("zero",pcm,0));assert(bounded.append_error()==pikoo::Playback::AppendError::Invalid);
  assert(bounded.append("a",pcm,240));
  assert(!bounded.append("b",pcm,1));assert(bounded.append_error()==pikoo::Playback::AppendError::Capacity);
  bounded.done("a");assert(!bounded.append("a",pcm,1));assert(bounded.append_error()==pikoo::Playback::AppendError::Completed);
  bounded.cancel();assert(!bounded.append("a",pcm,1));assert(bounded.append_error()==pikoo::Playback::AppendError::Rejected);
  std::cout<<"PASS: measured reconnect trace, startup deadline, short reply and stale audio; old starvation="
           <<previous.starved_ms<<" ms, fixed="<<fixed.starved_ms<<" ms\n";
}
