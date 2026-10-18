#pragma once
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace pikoo {
// Single producer. The worker may read output only after ready(), until the
// caller explicitly permits another trigger. reset() never touches that output.
class WakeReplay {
public:
  static constexpr size_t History=64000, Lookahead=9600, Silence=12800;
  static constexpr size_t Samples=History+Lookahead+Silence;
  WakeReplay(int16_t *history,int16_t *output):history_(history),output_(output){reset();}
  void reset(){std::fill_n(history_,History,0);head_=collected_=0;collecting_=ready_=false;}
  void append(const int16_t *pcm,size_t count){
    assert(count<=512);
    if(collecting_){
      auto n=std::min(count,Lookahead-collected_);
      std::copy_n(pcm,n,output_+History+collected_);collected_+=n;
      if(collected_==Lookahead){
        std::fill_n(output_+History+Lookahead,Silence,0);collecting_=false;ready_=true;
      }
    }
    auto n=std::min(count,History-head_);std::copy_n(pcm,n,history_+head_);
    std::copy_n(pcm+n,count-n,history_);head_=(head_+count)%History;
  }
  void trigger(){
    assert(!collecting_&&!ready_);
    std::copy_n(history_+head_,History-head_,output_);
    std::copy_n(history_,head_,output_+History-head_);
    collected_=0;collecting_=true;
  }
  bool ready()const{return ready_;}
  void release(){ready_=false;}
private:
  int16_t *history_,*output_;
  size_t head_=0,collected_=0;
  bool collecting_=false,ready_=false;
};
}
