// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_body.hpp"
#include <array>
#include <fstream>
#include <iostream>
using namespace pikoo;
int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--schemas") {
    auto o = Json(cJSON_CreateArray(), cJSON_Delete);
    for (auto &d : Body::definitions())
      cJSON_AddItemToArray(o.get(), parse(d).release());
    std::cout << json(o.get());
    return 0;
  }
  int db = -24, brightness = 100;
  Body body(
      [&](int v) {
        db = v;
        return Body::Applied{true, true, v};
      },
      [&](int v) {
        brightness = v;
        return Body::Applied{true, true, v};
      },
      [](const std::string &) { return true; });
  eyes::Animator animator;
  std::array<uint16_t, eyes::EyePixels * 2> pixels{};
  std::string line;
  while (std::getline(std::cin, line)) {
    auto r = parse(line);
    if (!r)
      return 2;
    auto ms = field(r.get(), "at_ms");
    uint64_t at = ms ? uint64_t(ms->valuedouble) : 0;
    if (auto tool = text(r.get(), "tool"); !tool.empty()) {
      auto args = field(r.get(), "arguments");
      std::cout << body.call(text(r.get(), "id"), tool, json(args), at)
                << std::endl;
    }
    auto file = text(r.get(), "frame");
    if (!file.empty()) {
      eyes::Input i;
      i.time_ms = at;
      i.state = eyes::State::Listening;
      body.input(i, at);
      auto p = animator.update(i);
      body.pose(p, at);
      for (int side = 0; side < 2; ++side)
        if (!eyes::render_fast(p, side, pixels.data() + side * eyes::EyePixels,
                               eyes::EyePixels))
          return 3;
      std::ofstream f(file, std::ios::binary);
      f << "P6\n480 240\n255\n";
      for (int y = 0; y < 240; ++y)
        for (int side = 0; side < 2; ++side)
          for (int x = 0; x < 240; ++x) {
            auto v = pixels[side * eyes::EyePixels + y * 240 + x];
            char rgb[] = {char(((v >> 11) & 31) * 255 / 31),
                          char(((v >> 5) & 63) * 255 / 63),
                          char((v & 31) * 255 / 31)};
            f.write(rgb, 3);
          }
      if (!f)
        return 4;
    }
  }
}
