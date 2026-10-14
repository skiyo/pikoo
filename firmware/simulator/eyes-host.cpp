#include "pikoo_eyes.hpp"
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

using namespace pikoo::eyes;
int main(int argc,char **argv) {
  std::array<uint16_t,EyePixels*2> pixels{};
  std::array<unsigned char,EyePixels*4> bytes{};
  Animator animator;
  auto draw=[&](Input input) {
    Pose p=animator.update(input);
    if(!render(p,0,pixels.data(),EyePixels) || !render(p,1,pixels.data()+EyePixels,EyePixels)) return false;
    for(std::size_t j=0;j<pixels.size();j++) { bytes[j*2]=pixels[j]&255; bytes[j*2+1]=pixels[j]>>8; }
    return true;
  };
  if(argc==5 && std::string(argv[1])=="--snapshot") {
    int state=0; double ms=0;
    try { state=std::stoi(argv[2]); ms=std::stod(argv[3]); } catch(...) { return 2; }
    if(state<0 || state>=StateCount || !std::isfinite(ms) || ms<0 || ms>1e12) return 2;
    if(!draw({static_cast<State>(state),ms,42,.3f,0,0})) return 2;
    std::ofstream f(argv[4],std::ios::binary); f<<"P6\n480 240\n255\n";
    for(int y=0;y<Height;y++) for(int side=0;side<2;side++) for(int x=0;x<Width;x++) {
      uint16_t v=pixels[side*EyePixels+y*Width+x];
      char rgb[3]={char(((v>>11)&31)*255/31),char(((v>>5)&63)*255/63),char((v&31)*255/31)};
      f.write(rgb,3);
    }
    return f.good()?0:1;
  }
  if(argc!=1) return 2;
  std::string line;
  while(std::getline(std::cin,line)) {
    if(line.size()>256) return 2;
    Input i; int state; uint64_t seed;
    std::istringstream in(line);
    if(!(in>>state>>i.time_ms>>seed>>i.level>>i.gaze_x>>i.gaze_y) || state<0 || state>=StateCount || seed>UINT32_MAX || !std::isfinite(i.time_ms) || i.time_ms<0 || i.time_ms>1e12 || !std::isfinite(i.level) || i.level<0 || i.level>1 || !std::isfinite(i.gaze_x) || std::abs(i.gaze_x)>1 || !std::isfinite(i.gaze_y) || std::abs(i.gaze_y)>1) return 2;
    std::string extra; if(in>>extra) return 2;
    i.state=static_cast<State>(state); i.seed=static_cast<uint32_t>(seed);
    if(!draw(i)) return 2;
    std::cout.write(reinterpret_cast<char*>(bytes.data()),bytes.size());std::cout.flush();
    if(!std::cout.good()) return 1;
  }
}
