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
  Pose p; p.state=i.state; p.time_ms=i.time_ms;
  float seconds=static_cast<float>(i.time_ms/1000.);
  float level=clamp(i.level,0,1);
  p.x=clamp(i.gaze_x,-1,1)*18; p.y=clamp(i.gaze_y,-1,1)*12;
  p.blink=blink(i.time_ms,i.seed);
  switch (i.state) {
    case State::Boot: p.open=.65f; p.ring=.7f; break;
    case State::Idle:
      p.x+=std::sin(seconds*.43f+noise(i.seed)*3)*7;
      p.y+=std::sin(seconds*.31f)*3; p.open=.75f; break;
    case State::Connecting: p.open=.98f; p.pupil=36; p.ring=.8f; break;
    case State::Listening: p.open=.98f; p.pupil=34+level*6; p.ring=.32f+level*.2f; break;
    case State::Thinking: p.y-=12; p.x+=std::sin(seconds*1.5f)*3; p.open=.8f; p.ring=.5f; break;
    case State::Speaking: p.open=.88f+level*.1f; p.pupil=33+level*5; p.y-=level*2; p.ring=.3f+level*.4f; break;
    case State::Muted: p.open=.48f; p.saturation=.08f; p.pupil=29; break;
    case State::Offline: p.open=.6f; p.x-=5; p.saturation=.5f; p.ring=.35f; break;
    case State::Occupied: p.x+=15; p.open=.72f; p.ring=.25f; break;
    case State::AuthError: p.open=.66f; p.tilt=.07f; p.saturation=.5f; p.ring=.55f; break;
    case State::Happy: p.open=.82f; p.smile=1; p.pupil=37; p.ring=.5f; break;
    case State::Drowsy: p.open=.3f; p.y+=6; p.pupil=28; break;
    case State::Curious: p.x+=12; p.y-=7; p.open=1; p.pupil=39; p.tilt=.05f; break;
  }
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
  Color bg=color(0x171714), white=color(0xFFF1D9), iris=color(0xCD9148), rim=color(0x8D592E), pupil=color(0x2D211C);
  Color a=accent(p.state);
  float cx=120+clamp(p.x,-32,32)+(side?-.8f:.8f), cy=120+clamp(p.y,-24,24);
  float open=clamp(p.open,.05f,1)*(1-clamp(p.blink,0,1));
  float radius=clamp(p.pupil,22,46);
  for (int y=0;y<Height;y++) for(int x=0;x<Width;x++) {
    float dx=x-119.5f,dy=y-119.5f,disc=std::sqrt(dx*dx+dy*dy);
    if (disc>=119.5f) { out[y*Width+x]=0; continue; }
    Color c=bg;
    // A restrained inner status ring leaves the artwork room to breathe.
    float ring_cover=cover(std::abs(disc-113)-.8f)*clamp(p.ring,0,1);
    if (p.state==State::Connecting || p.state==State::Boot) {
      float ang=std::atan2(dy,dx)+static_cast<float>(std::fmod(p.time_ms*.0018,2*Pi));
      ring_cover*=.25f+.75f*(std::sin(ang)*.5f+.5f);
    }
    c=mix(c,a,ring_cover);
    float ellipse=(dx*dx/(99*99.f)+dy*dy/(95*95.f)-1)*45;
    float upper=-open*85 + dx*dx*.0014f + clamp(p.tilt,-.1f,.1f)*dx*(side?1:-1);
    float lower=open*85 - clamp(p.smile,0,1)*(36-dx*dx*.0025f);
    float mask=std::min(cover(ellipse),std::min(cover(upper-dy),cover(dy-lower)));
    if (mask>0) {
      Color eye=mix(white,color(0xEBCFA7),clamp((dy+65)/220,0,.23f));
      float ix=x-cx,iy=y-cy,ir=std::sqrt(ix*ix+iy*iy);
      Color amber=mix(iris,rim,clamp((ir-35)/30,0,1)*.55f);
      amber=mix(amber,color(0xE2B56B),clamp((-iy-5)/100,0,.25f));
      eye=mix(eye,amber,cover(ir-65));
      eye=mix(eye,rim,cover(std::abs(ir-64)-1.4f)*.6f);
      eye=mix(eye,pupil,cover(ir-radius));
      float h1=std::sqrt((ix+15)*(ix+15)+(iy+22)*(iy+22));
      float h2=std::sqrt((ix-15)*(ix-15)+(iy-18)*(iy-18));
      eye=mix(eye,color(0xFFF9EA),cover(h1-8)*.95f);
      eye=mix(eye,color(0xFFF9EA),cover(h2-3.5f)*.7f);
      c=mix(c,eye,mask);
    }
    if (open<.08f) c=mix(c,rim,cover(std::abs(dy-(dx*dx*.0014f))-1.3f)*cover(std::abs(dx)-76));
    float gray=c.r*.3f+c.g*.59f+c.b*.11f;
    c=mix({gray,gray,gray},c,clamp(p.saturation,0,1));
    unsigned r=static_cast<unsigned>(clamp(c.r,0,255)+.5f),g=static_cast<unsigned>(clamp(c.g,0,255)+.5f),b=static_cast<unsigned>(clamp(c.b,0,255)+.5f);
    out[y*Width+x]=static_cast<uint16_t>(((r>>3)<<11)|((g>>2)<<5)|(b>>3));
  }
  return true;
}
} // namespace pikoo::eyes
