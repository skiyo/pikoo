// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_eyes.hpp"
#include <algorithm>
#include <array>
#include <cmath>
namespace pikoo::eyes {
namespace {
float cap(float x,float a,float b){return std::clamp(x,a,b);}
uint16_t rgb(unsigned value,float saturation){
  float r=(value>>16)&255,g=(value>>8)&255,b=value&255;
  float gray=r*.3f+g*.59f+b*.11f;
  unsigned ri=gray+(r-gray)*saturation+.5f,gi=gray+(g-gray)*saturation+.5f,bi=gray+(b-gray)*saturation+.5f;
  return ((ri>>3)<<11)|((gi>>2)<<5)|(bi>>3);
}
uint16_t blend(uint16_t bg,uint16_t fg,float amount){
  int a=static_cast<int>(cap(amount,0,1)*256);
  int r=((bg>>11)*(256-a)+(fg>>11)*a)>>8;
  int g=(((bg>>5)&63)*(256-a)+((fg>>5)&63)*a)>>8;
  int b=((bg&31)*(256-a)+(fg&31)*a)>>8;
  return (r<<11)|(g<<5)|b;
}
struct Raster {
  uint16_t *pixels;
  std::array<int,240> left,right;
  void pixel(int x,int y,uint16_t color,float alpha=1){
    if(alpha<=0||y<0||y>=240||x<left[y]||x>right[y])return;
    auto &p=pixels[y*240+x];p=alpha>=1?color:blend(p,color,alpha);
  }
  void span(int y,float l,float r,uint16_t color){
    if(y<0||y>=240||l>r)return;
    int a=std::max(left[y],static_cast<int>(std::ceil(l-.5f)));
    int b=std::min(right[y],static_cast<int>(std::floor(r+.5f)));
    if(a>b)return;
    auto *row=pixels+y*240;
    uint16_t old_a=row[a],old_b=row[b];
    std::fill(row+a,row+b+1,color);
    float alpha_a=std::min(1.f,std::min(a-l+.5f,r-a+.5f));
    row[a]=alpha_a>=1?color:blend(old_a,color,alpha_a);
    if(b!=a){
      float alpha_b=std::min(1.f,std::min(b-l+.5f,r-b+.5f));
      row[b]=alpha_b>=1?color:blend(old_b,color,alpha_b);
    }
  }
  void ellipse(float cx,float cy,float rx,float ry,uint16_t color){
    if(rx<=0||ry<=0)return;
    int first=std::max(0,int(std::ceil(cy-ry))),last=std::min(239,int(std::floor(cy+ry)));
    for(int y=first;y<=last;y++){
      float q=(y-cy)/ry;
      float width=rx*std::sqrt(std::max(0.f,1-q*q));
      span(y,cx-width,cx+width,color);
    }
  }
};
}
bool render_fast(const Pose &p,int side,uint16_t *out,std::size_t count){
  if(!out||count<EyePixels||side<0||side>1||
     !std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.open)||!std::isfinite(p.pupil)||
     !std::isfinite(p.tilt)||!std::isfinite(p.smile)||!std::isfinite(p.blink)||
     !std::isfinite(p.saturation)||!std::isfinite(p.ring)||!std::isfinite(p.time_ms))return false;
  const float sat=cap(p.saturation,0,1),opening=cap(p.open,0,1)*(1-cap(p.blink,0,1));
  auto bg=rgb(0x252427,sat),white=rgb(0xFFF8EB,sat),amber=rgb(0xEDBD70,sat),dark=rgb(0x332A29,sat),shine=rgb(0xFFFCF3,sat);
  float cx=119.5f+cap(p.x,-28,28)+(side?-.7f:.7f);
  float cy=119.5f+cap(p.y,-22,22)+cap(p.tilt,-.1f,.1f)*(side?35:-35);
  Raster r{out,{}, {}};
  std::fill_n(out,EyePixels,0);
  // One square root per scanline, instead of per pixel.
  for(int y=0;y<240;y++){
    float dy=y-119.5f;
    float width=std::sqrt(std::max(0.f,119.5f*119.5f-dy*dy));
    r.left[y]=std::max(0,int(std::ceil(119.5f-width+.0001f)));
    r.right[y]=std::min(239,int(std::floor(119.5f+width-.0001f)));
    if(r.right[y]>=r.left[y])std::fill(out+y*240+r.left[y],out+y*240+r.right[y]+1,bg);
  }
  auto physical_left=r.left,physical_right=r.right;
  if(opening>.035f){
    r.ellipse(119.5f,119.5f,119.5f,119.5f*opening,white);
    for(int y=0;y<240;y++){
      float q=(y-119.5f)/(119.5f*opening);
      if(std::abs(q)>1){r.left[y]=240;r.right[y]=-1;continue;}
      float width=119.5f*std::sqrt(std::max(0.f,1-q*q));
      r.left[y]=std::max(r.left[y],int(std::ceil(119.5f-width)));
      r.right[y]=std::min(r.right[y],int(std::floor(119.5f+width)));
    }
    r.ellipse(cx,cy,81,81,amber);
    float smile=cap(p.smile,0,1);
    if(smile<1)r.ellipse(cx,cy,cap(p.pupil,40,58),cap(p.pupil,40,58)*(1-smile),dark);
    if(smile>0){
      for(int x=int(cx-53);x<=int(cx+53);x++){
        float ix=x-cx,q=cap(ix,-43,43),arch=-10+q*q*.014f;
        for(int y=int(cy+arch-10);y<=int(cy+arch+10);y++){
          float d=std::sqrt((ix-q)*(ix-q)+(y-cy-arch)*(y-cy-arch));
          r.pixel(x,y,dark,cap(.5f-(d-9)/1.3f,0,1)*smile);
        }
      }
    }
    if(smile<.5f){r.ellipse(cx-22,cy-25,18,22,shine);r.ellipse(cx+23,cy+24,7,7,shine);}
  }
  r.left=physical_left;r.right=physical_right;
  if(opening<.09f){
    auto closed=rgb(0xEAC898,sat);float opacity=cap((.09f-opening)/.055f,0,1);
    for(int x=int(cx-82);x<=int(cx+82);x++){
      float lx=x-cx,q=cap(lx,-77,77),curve=5+(77*77-q*q)*.0023f;
      for(int y=int(cy+curve-6);y<=int(cy+curve+6);y++){
        float delta=y-cy-curve;
        float d=lx==q?std::abs(delta):std::sqrt((lx-q)*(lx-q)+delta*delta);
        r.pixel(x,y,closed,cap(.5f-(d-3.2f)/1.3f,0,1)*opacity);
      }
    }
  }
  unsigned color=0xCCA468;
  if(p.state==State::Listening)color=0x9BB7A2;
  if(p.state==State::Thinking)color=0xAD9DBF;
  if(p.state==State::Speaking||p.state==State::Happy)color=0xD9A17E;
  if(p.state==State::Muted)color=0x807C76;
  auto accent=rgb(color,sat);
  for(int y=1;y<239&&p.ring>0;y++){
    float dy=y-119.5f;
    // Only the thin ring boundary needs distance/angle shading.
    for(int edge=0;edge<2;edge++){
      float outer=std::sqrt(std::max(0.f,118.6f*118.6f-dy*dy));
      float inner=std::sqrt(std::max(0.f,116.4f*116.4f-dy*dy));
      int first=int(std::floor(119.5f+(edge?inner:-outer)))-1;
      int last=int(std::ceil(119.5f+(edge?outer:-inner)))+1;
      for(int x=first;x<=last;x++){
        float dx=x-119.5f,d=std::sqrt(dx*dx+dy*dy);
        float alpha=cap(.5f-(std::abs(d-117.5f)-.6f),0,1)*cap(p.ring,0,1);
        if(p.state==State::Connecting||p.state==State::Boot)
          alpha*=.25f+.75f*(std::sin(std::atan2(dy,dx)+float(std::fmod(p.time_ms*.0018,6.2831853)))*.5f+.5f);
        r.pixel(x,y,accent,alpha);
      }
    }
  }
  return true;
}
}
