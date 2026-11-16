#pragma once
#include "pikoo_eyes.hpp"

namespace board {
// Directions follow the user's view facing the installed DualEye screens.
// The panel wiring exchanges the eyes, and mounting reverses horizontal gaze.
inline pikoo::eyes::Pose mounted_pose(pikoo::eyes::Pose pose) {
  pose.x = -pose.x;
  if (pose.blink_side == 0 || pose.blink_side == 1)
    pose.blink_side = 1 - pose.blink_side;
  return pose;
}
} // namespace board
