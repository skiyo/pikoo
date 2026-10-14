#include "pikoo_eyes.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <set>
using namespace pikoo::eyes;
uint64_t checksum(const uint16_t *p) { uint64_t h=1469598103934665603ULL;for(std::size_t i=0;i<EyePixels;i++){h^=p[i];h*=1099511628211ULL;}return h; }
int main(){
 std::array<uint16_t,EyePixels+2> a{},b{};std::set<uint64_t> seen;
 for(int state=0;state<StateCount;state++){
  Animator animator,second;Input i{static_cast<State>(state),1000,42,.3f,0,0};auto pose=animator.update(i);
  a.front()=a.back()=0x1234;assert(render(pose,0,a.data()+1,EyePixels));
  assert(a.front()==0x1234&&a.back()==0x1234);
  assert(render(second.update(i),0,b.data()+1,EyePixels));assert(a==b || (a.front()==0x1234&&checksum(a.data()+1)==checksum(b.data()+1)));
  seen.insert(checksum(a.data()+1));
  for(int y=0;y<240;y++)for(int x=0;x<240;x++){float dx=x-119.5f,dy=y-119.5f;if(dx*dx+dy*dy>=119.5f*119.5f)assert(a[1+y*240+x]==0);}
  assert(render(pose,1,b.data()+1,EyePixels));assert(checksum(a.data()+1)!=checksum(b.data()+1));
  assert(!render(pose,2,a.data(),EyePixels));assert(!render(pose,0,nullptr,EyePixels));assert(!render(pose,0,a.data(),EyePixels-1));
  pose.x=std::numeric_limits<float>::quiet_NaN();assert(!render(pose,0,a.data(),EyePixels));
 }
 assert(seen.size()==StateCount);
 Animator animator;auto idle=animator.update({State::Idle,1000});auto initial=animator.update({State::Listening,1050});assert(initial.open==idle.open);
 auto middle=animator.update({State::Listening,1160});assert(middle.open>idle.open&&middle.open<.98f);
 auto end=animator.update({State::Listening,1270});assert(std::abs(end.open-.98f)<.001);
 double previous=-1,blinkStart=-1;bool blinking=false;int count=0;
 animator.reset();for(int ms=0;ms<60000;ms++){auto p=animator.update({State::Idle,double(ms),42});bool now=p.blink>0;if(now&&!blinking){blinkStart=ms;if(previous>=0){assert(ms-previous>=3000&&ms-previous<=5000);}previous=ms;count++;}if(!now&&blinking)assert(ms-blinkStart>=149&&ms-blinkStart<=151);blinking=now;}
 assert(count>=14);std::cout<<"13 deterministic states, bounds, crop, binocular gaze, 220ms transition and 3..5s/150ms blink passed\n";
}
