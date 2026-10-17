#include "pikoo_eyes.hpp"
#include <algorithm>
#include <cmath>

namespace pikoo::eyes {
namespace {
constexpr float Pi = 3.14159265358979323846f;
float clamp(float x, float lo, float hi) { return std::clamp(x, lo, hi); }
float lerp(float a, float b, float x) { return a + (b-a)*x; }
uint32_t hash(uint32_t x) { x ^= x>>16; x *= 0x7feb352d; x ^= x>>15; x *= 0x846ca68b; return x^(x>>16); }
float noise(uint32_t n) { return (hash(n) & 65535)/65535.f; }
float blink(double t, uint32_t seed) {
  // Each 4-second cycle contains one blink, spaced 3..5 seconds apart.
  auto cycle = static_cast<uint32_t>(t/4000.);
  double when = cycle*4000. + 2500. + 1000.*noise(seed+cycle);
  double age = t-when;
  if (age<0 || age>150) return 0;
  return static_cast<float>(std::sin(Pi*age/150.));
}
struct Color { float r,g,b; };
Color color(int hex) { return {float(hex>>16 & 255), float(hex>>8 & 255), float(hex & 255)}; }
Color mix(Color a, Color b, float f) { f=clamp(f,0,1); return {lerp(a.r,b.r,f),lerp(a.g,b.g,f),lerp(a.b,b.b,f)}; }
float cover(float signed_distance) { return clamp(.5f-signed_distance,0,1); }
Color accent(State s) {
  if (s==State::Listening) return color(0x9BB7A2);
  if (s==State::Thinking) return color(0xAD9DBF);
  if (s==State::Speaking || s==State::Happy) return color(0xD9A17E);
  if (s==State::Muted) return color(0x807C76);
  return color(0xCCA468);
}
Pose target(const Input &i) {
  Pose p; p.state=i.state; p.time_ms=i.time_ms; p.open=1; p.pupil=49;
  float seconds=static_cast<float>(i.time_ms/1000.);
  float level=clamp(i.level,0,1);
  p.x=clamp(i.gaze_x,-1,1)*18; p.y=clamp(i.gaze_y,-1,1)*12;
  p.blink=(i.state==State::Idle||i.state==State::Muted)?0:blink(i.time_ms,i.seed);
  switch (i.state) {
    case State::Boot: p.open=0; p.ring=.6f; break;
    case State::Idle: p.open=0; p.y=std::sin(seconds*.7f)*.7f; break;
    case State::Connecting: p.open=0; p.pupil=53; p.ring=.7f; break;
    case State::Listening: p.pupil=50+level*4; p.ring=.2f+level*.15f; break;
    case State::Thinking: p.y-=12; p.x+=std::sin(seconds*1.5f)*3; p.pupil=47; p.ring=.3f; break;
    case State::Speaking: p.pupil=50+level*4; p.y-=level*2; p.ring=.2f+level*.3f; break;
    case State::Muted: p.open=0; p.saturation=.08f; break;
    case State::Offline: p.open=0; p.x-=5; p.pupil=46; p.saturation=.65f; p.ring=.25f; break;
    case State::Occupied: p.open=0; p.x+=15; p.pupil=46; p.ring=.25f; break;
    case State::AuthError: p.open=0; p.tilt=.08f; p.pupil=46; p.saturation=.5f; p.ring=.45f; break;
    case State::Happy: p.smile=1; p.pupil=52; p.ring=.3f; break;
    case State::Drowsy: p.open=.28f; p.y+=5; p.pupil=46; break;
    case State::Curious: p.x+=12; p.y-=7; p.pupil=55; p.tilt=.08f; break;
  }
  if(p.open==0)p.blink=0;
  return p;
}
}
void Animator::reset() { last_time_=-1; }
Pose Animator::update(const Input &i) {
  if (static_cast<int>(i.state)<0 || static_cast<int>(i.state)>=StateCount ||
      !std::isfinite(i.time_ms) || i.time_ms<0 || i.time_ms>1e12 ||
      !std::isfinite(i.level) || !std::isfinite(i.gaze_x) || !std::isfinite(i.gaze_y)) return previous_;
  Pose p=target(i);
  if (last_time_<0 || i.time_ms<last_time_) { previous_=start_=p; state_=i.state; changed_at_=i.time_ms-220; }
  if (i.state!=state_) { start_=previous_; state_=i.state; changed_at_=i.time_ms; }
  float f=clamp(static_cast<float>((i.time_ms-changed_at_)/220.),0,1);
  f=f*f*(3-2*f);
  p.x=lerp(start_.x,p.x,f); p.y=lerp(start_.y,p.y,f);
  p.open=lerp(start_.open,p.open,f); p.pupil=lerp(start_.pupil,p.pupil,f);
  p.tilt=lerp(start_.tilt,p.tilt,f); p.smile=lerp(start_.smile,p.smile,f);
  p.saturation=lerp(start_.saturation,p.saturation,f); p.ring=lerp(start_.ring,p.ring,f);
  previous_=p; last_time_=i.time_ms; return p;
}
bool render(const Pose &p,int side,uint16_t *out,std::size_t count) {
  if (!out || count<EyePixels || side<0 || side>1 ||
      !std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.open) ||
      !std::isfinite(p.pupil) || !std::isfinite(p.tilt) || !std::isfinite(p.smile) ||
      !std::isfinite(p.blink) || !std::isfinite(p.saturation) || !std::isfinite(p.ring) ||
      !std::isfinite(p.time_ms)) return false;
  Color bg=color(0x252427), white=color(0xFFF8EB), iris=color(0xEDBD70), pupil=color(0x332A29);
  Color a=accent(p.state);
  float cx=119.5f+clamp(p.x,-28,28)+(side?-.7f:.7f);
  float cy=119.5f+clamp(p.y,-22,22)+clamp(p.tilt,-.1f,.1f)*(side?35:-35);
  float open=clamp(p.open,0,1)*(1-clamp(p.blink,0,1));
  float radius=clamp(p.pupil,40,58);
  for (int y=0;y<Height;y++) for(int x=0;x<Width;x++) {
    float dx=x-119.5f,dy=y-119.5f,disc=std::sqrt(dx*dx+dy*dy);
    if (disc>=119.5f) { out[y*Width+x]=0; continue; }
    Color c=bg;
    // Opening is a rounded ellipse, rather than two straight black eyelid masks.
    // At full openness the entire circular display is the eyeball.
    float mask=0;
    if(open>=.999f)mask=1;
    else if(open>.035f){float ey=dy/open;mask=cover((std::sqrt(dx*dx+ey*ey)-119.5f)*open/1.2f);}
    if(mask>0){
      float ix=x-cx,iy=y-cy,ir=std::sqrt(ix*ix+iy*iy);
      Color eye=white;
      Color amber=iris;
      eye=mix(eye,amber,cover((ir-81)/1.4f));
      float round_pupil=cover((ir-radius)/1.3f);
      float q=clamp(ix,-43,43),arch=-10+q*q*.014f;
      float smile_pupil=cover((std::sqrt((ix-q)*(ix-q)+(iy-arch)*(iy-arch))-9)/1.3f);
      eye=mix(eye,pupil,lerp(round_pupil,smile_pupil,clamp(p.smile,0,1)));
      float h1=(std::sqrt((ix+22)*(ix+22)/324+(iy+25)*(iy+25)/484)-1)*18;
      float h2=std::sqrt((ix-23)*(ix-23)+(iy-24)*(iy-24))-7;
      float shine=(1-clamp(p.smile,0,1));
      eye=mix(eye,color(0xFFFCF3),cover(h1/1.3f)*shine);
      eye=mix(eye,color(0xFFFCF3),cover(h2/1.3f)*.85f*shine);
      c=mix(c,eye,mask);
    }
    // Soft, round-ended sleeping arcs; also provide a clean closed blink frame.
    if(open<.09f){
      float lx=x-cx,q=clamp(lx,-77,77),curve=5+(77*77-q*q)*.0023f;
      float distance=std::sqrt((lx-q)*(lx-q)+(y-cy-curve)*(y-cy-curve));
      c=mix(c,color(0xEAC898),cover((distance-3.2f)/1.3f)*clamp((.09f-open)/.055f,0,1));
    }
    // Status remains subtle and lives at the circular perimeter, never as a bar.
    float ring_cover=cover(std::abs(disc-117.5f)-.6f)*clamp(p.ring,0,1);
    if(p.state==State::Connecting||p.state==State::Boot){float ang=std::atan2(dy,dx)+static_cast<float>(std::fmod(p.time_ms*.0018,2*Pi));ring_cover*=.25f+.75f*(std::sin(ang)*.5f+.5f);}
    c=mix(c,a,ring_cover);
    float gray=c.r*.3f+c.g*.59f+c.b*.11f;
    c=mix({gray,gray,gray},c,clamp(p.saturation,0,1));
    unsigned r=static_cast<unsigned>(clamp(c.r,0,255)+.5f),g=static_cast<unsigned>(clamp(c.g,0,255)+.5f),b=static_cast<unsigned>(clamp(c.b,0,255)+.5f);
    out[y*Width+x]=static_cast<uint16_t>(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
  }
  return true;
}
} // namespace pikoo::eyes
