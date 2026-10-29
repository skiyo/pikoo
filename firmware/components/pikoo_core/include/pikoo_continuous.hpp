#pragma once
#include <cstdint>
#include <string>
namespace pikoo {
// Transport metadata only: audio packet gaps are never response completion.
class ContinuousStream {
 public:
  void ready(const std::string &stream,uint32_t generation) {id=stream;epoch=generation;next=0;enabled=!stream.empty();}
  void clear(uint32_t generation) {epoch=generation;id.clear();next=0;enabled=false;}
  bool accept(const std::string &stream,uint32_t generation,uint32_t sequence) {
    if(!enabled||stream!=id||generation!=epoch||sequence!=next)return false;
    ++next;return true;
  }
  std::string id;
  uint32_t epoch=0,next=0;
  bool enabled=false;
};
}
