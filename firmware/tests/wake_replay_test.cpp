#include "pikoo_wake_replay.hpp"
#include "pikoo_phonetic.hpp"
#include <cassert>
#include <limits>
#include <vector>
int main(){
  using R=pikoo::WakeReplay;
  std::vector<int16_t> history(R::History),output(R::Samples,-1),chunk(512);
  R replay(history.data(),output.data());
  for(size_t i=0;i<512;++i)chunk[i]=int16_t(i+1);
  replay.append(chunk.data(),512);replay.trigger();
  for(size_t i=0;i<R::History-512;++i)assert(output[i]==0);
  for(size_t i=0;i<512;++i)assert(output[R::History-512+i]==chunk[i]);
  for(unsigned block=0;block<19;++block){
    std::fill(chunk.begin(),chunk.end(),int16_t(block+1));replay.append(chunk.data(),512);
    assert(replay.ready()==(block==18));
  }
  assert(output[R::History+R::Lookahead-1]==19);
  for(size_t i=R::History+R::Lookahead;i<R::Samples;++i)assert(output[i]==0);
  auto held=output;replay.reset();assert(output==held); // Cancellation cannot overwrite worker input.
  for(unsigned block=0;block<130;++block){std::fill(chunk.begin(),chunk.end(),int16_t(block));replay.append(chunk.data(),512);}
  replay.trigger();assert(output[0]==5&&output[R::History-1]==129);
  pikoo::PhoneticDecision decision;
  assert(!decision.rejected());assert(decision.observe(1,.7f));assert(decision.observe(2,.6f));assert(!decision.rejected());
  assert(decision.observe(2,.8f));assert(decision.rejected());
  assert(decision.observe(5,.9f));assert(!decision.rejected());
  assert(!decision.observe(2,std::numeric_limits<float>::quiet_NaN()));assert(decision.top_id==5);
}
