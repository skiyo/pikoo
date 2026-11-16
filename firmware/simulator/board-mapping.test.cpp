#include "../main/board_display_mapping.hpp"
#include <cassert>
#include <iostream>
int main() {
  pikoo::eyes::Pose p{};
  p.x = -18;
  p.y = 7;
  p.open = .8f;
  p.command_blink = 1;
  p.blink_side = 0;
  auto left = board::mounted_pose(p);
  assert(left.x == 18 && left.blink_side == 1);
  assert(left.y == p.y && left.open == p.open && left.command_blink == 1);
  p.x = 18;
  p.blink_side = 1;
  auto right = board::mounted_pose(p);
  assert(right.x == -18 && right.blink_side == 0);
  p.x = 0;
  p.blink_side = -1;
  auto both = board::mounted_pose(p);
  assert(both.x == 0 && both.blink_side == -1);
  std::cout << "Installed DualEye left/right wink and gaze mapping passed\n";
}
