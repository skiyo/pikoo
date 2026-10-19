#include "pikoo_eyes.hpp"
#ifdef PIKOO_EYES_FAST_TEST
#define render render_fast
#endif
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
#ifdef PIKOO_EYES_FAST_TEST
 // A clipped redraw must exactly match a complete frame within its band and
 // preserve every outside pixel, for all states and both display sides.
 for(int state=0;state<StateCount;state++)for(int side=0;side<2;side++){
  Animator clipped;auto p=clipped.update({static_cast<State>(state),3200,42,.4f});
  assert(render(p,side,a.data(),EyePixels));
  std::fill(b.begin(),b.end(),0xa55a);
  assert(render_fast_rows(p,side,b.data(),EyePixels,80,180));
  for(std::size_t pixel=0;pixel<EyePixels;pixel++)
   assert(b[pixel]==(pixel>=80*240&&pixel<180*240?a[pixel]:0xa55a));
  assert(!render_fast_rows(p,side,b.data(),EyePixels,-1,180));
  assert(!render_fast_rows(p,side,b.data(),EyePixels,80,241));
  assert(!render_fast_rows(p,side,b.data(),EyePixels,80,80));
 }
 // For extreme closed-eye gaze/tilt, no changed pixel may lie outside the
 // union of old/new damage bounds. This checks against actual full rasters.
 Pose closed_pose;assert(closed_eye_rows(closed_pose).last-closed_eye_rows(closed_pose).first<40);
 for(float y:{-22.f,0.f,22.f})for(float tilt:{-.1f,0.f,.1f})for(int side=0;side<2;side++){
  Pose old_pose,new_pose;old_pose.y=-y;old_pose.tilt=-tilt;new_pose.y=y;new_pose.tilt=tilt;new_pose.x=28;
  auto old_rows=closed_eye_rows(old_pose),new_rows=closed_eye_rows(new_pose);
  int first=std::min(old_rows.first,new_rows.first),last=std::max(old_rows.last,new_rows.last);
  assert(render(old_pose,side,a.data(),EyePixels)&&render(new_pose,side,b.data(),EyePixels));
  for(std::size_t pixel=0;pixel<EyePixels;pixel++)
   if(a[pixel]!=b[pixel])assert(pixel>=std::size_t(first*240)&&pixel<std::size_t(last*240));
 }
#endif
 // Awake eyeballs fill the disc at the top/bottom; no persistent black bars.
 Animator awake;auto listening=awake.update({State::Listening,1000});assert(render(listening,0,a.data(),EyePixels));
 auto bright=[](uint16_t c){return ((c>>11)&31)>24&&((c>>5)&63)>50;};
 assert(bright(a[20*240+120])&&bright(a[220*240+120]));
 Animator sleeping;auto idle_pose=sleeping.update({State::Idle,1000});assert(idle_pose.open==0&&idle_pose.blink==0);
 for(auto state:{State::Boot,State::Idle,State::Connecting,State::Muted,State::Offline,State::Occupied,State::AuthError}){
  Animator closed;auto p=closed.update({state,3200});assert(p.open==0&&p.blink==0);
 }

 Animator animator;auto idle=animator.update({State::Idle,1000});auto initial=animator.update({State::Listening,1050});assert(initial.open==idle.open);
 assert(idle.open==0&&idle.blink==0);
 auto middle=animator.update({State::Listening,1160});assert(middle.open>idle.open&&middle.open<1);
 auto end=animator.update({State::Listening,1270});assert(std::abs(end.open-1)<.001);
 double previous=-1,blinkStart=-1;bool blinking=false;int count=0;
 animator.reset();for(int ms=0;ms<60000;ms++){auto p=animator.update({State::Listening,double(ms),42});bool now=p.blink>0;if(now&&!blinking){blinkStart=ms;if(previous>=0){assert(ms-previous>=3000&&ms-previous<=5000);}previous=ms;count++;}if(!now&&blinking)assert(ms-blinkStart>=149&&ms-blinkStart<=151);blinking=now;}
 assert(count>=14);std::cout<<"13 deterministic states, bounds, crop, binocular gaze, 220ms transition and 3..5s/150ms blink passed\n";
}
