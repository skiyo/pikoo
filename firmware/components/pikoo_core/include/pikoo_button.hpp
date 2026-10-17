#pragma once
#include <cstdint>
namespace pikoo {
class Button {
 public:
  enum Action { None, Press, Double, Hold };
  Action update(bool down, uint64_t now) {
    if (down!=raw_) {raw_=down;changed_=now;}
    if (raw_!=stable_ && now-changed_>=25) {
      stable_=raw_;
      if(stable_) {
        pressed_=now;held_=false;
        if(have_click_ && now-last_click_<=350) {have_click_=false;return Double;}
        have_click_=true;last_click_=now;return Press;
      }
    }
    if(stable_ && !held_ && now-pressed_>=2000) {
      held_=true;have_click_=false;return Hold;
    }
    return None;
  }
 private:
  bool raw_=false,stable_=false,held_=false,have_click_=false;
  uint64_t changed_=0,pressed_=0,last_click_=0;
};
}
