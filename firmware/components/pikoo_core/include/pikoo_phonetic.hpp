#pragma once
#include <algorithm>
#include <array>
#include <cmath>

namespace pikoo {
inline constexpr std::array<const char *,10> PhoneticCommands={
  "ni hao pi ku","ni hao pi qiu","ni hao ku ku","ni zhen ku","ni hao pi ke",
  "gei wo jiang yi ge gu shi","wo de ji mu bu jian le","jin tian tian qi zhen hao","wan an","zai jian"};
// Versioned experimental policy. Unknown and ambiguous pi-ke retain the primary
// whole-phrase decision. This is never a stand-alone wake-word recognizer.
struct PhoneticDecision {
  int top_id=0;
  float probability=0,target_peak=0;
  bool observe(int id,float p){
    if(id<1||id>10||!std::isfinite(p)||p<0||p>1)return false;
    if(p>probability){probability=p;top_id=id;}
    if(id==1)target_peak=std::max(target_peak,p);
    return true;
  }
  bool rejected(float cutoff=.5f)const{
    return probability>=cutoff&&(top_id==2||top_id==3||top_id==4||(top_id>=6&&top_id<=10));
  }
};
}
