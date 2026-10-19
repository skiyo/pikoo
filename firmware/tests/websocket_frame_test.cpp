// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_websocket_frame.hpp"
#include <array>
#include <algorithm>
#include <cassert>
#include <vector>
#include <iostream>
int main() {
  const uint8_t mask[]{0x37,0xfa,0x21,0x3d};
  const uint8_t hello[]{'H','e','l','l','o'};
  const uint8_t example[]{0x81,0x85,0x37,0xfa,0x21,0x3d,0x7f,0x9f,0x4d,0x51,0x58};
  std::array<uint8_t,32> out{};
  assert(pikoo::client_frame(0x81,hello,5,mask,out.data(),out.size())==sizeof(example));
  assert(std::equal(std::begin(example),std::end(example),out.begin()));
  for (std::size_t count : {0u,1u,125u,126u,8192u,65535u}) {
    std::vector<uint8_t> input(count),output(count+10,0xa5);
    for(std::size_t i=0;i<count;++i)input[i]=i*17;
    auto before=input;
    auto n=pikoo::client_frame(0x82,input.data(),count,mask,output.data()+1,output.size()-2);
    assert(n==count+(count<126?6:8));
    assert(output.front()==0xa5&&output[n+1]==0xa5&&input==before);
    const auto *frame=output.data()+1;
    assert(frame[0]==0x82&&(frame[1]&0x80));
    std::size_t header=2,size=frame[1]&127;
    if(size==126){size=(std::size_t(frame[2])<<8)|frame[3];header=4;}
    assert(size==count);
    for(std::size_t i=0;i<count;++i)assert((frame[header+4+i]^frame[header+i%4])==input[i]);
  }
  assert(pikoo::client_frame(0x89,nullptr,0,mask,out.data(),out.size())==6);
  assert(!pikoo::client_frame(0x09,hello,5,mask,out.data(),out.size()));
  assert(!pikoo::client_frame(0xc1,hello,5,mask,out.data(),out.size()));
  assert(!pikoo::client_frame(0x83,hello,5,mask,out.data(),out.size()));
  assert(!pikoo::client_frame(0x81,nullptr,5,mask,out.data(),out.size()));
  assert(!pikoo::client_frame(0x81,hello,5,mask,out.data(),10));
  assert(!pikoo::client_frame(0x89,hello,126,mask,out.data(),out.size()));
  assert(!pikoo::client_frame(0x81,hello,65536,mask,out.data(),out.size()));
  std::cout<<"RFC client masking, boundary lengths, control frames, bounds and immutable input passed\n";
}
