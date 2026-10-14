#pragma once
#include <cstddef>
#include <cstdint>

// Original Pikoo artwork. No ESP-IDF, LVGL, heap or platform dependencies.
namespace pikoo::eyes {
constexpr int Width = 240, Height = 240;
constexpr std::size_t EyePixels = Width * Height;
enum class State { Boot, Idle, Connecting, Listening, Thinking, Speaking,
                   Muted, Offline, Occupied, AuthError, Happy, Drowsy, Curious };
constexpr int StateCount = 13;
struct Input {
  State state = State::Idle;
  double time_ms = 0;
  uint32_t seed = 42;
  float level = 0, gaze_x = 0, gaze_y = 0;
};
struct Pose {
  float x = 0, y = 0, open = .82f, pupil = 32, tilt = 0,
        smile = 0, blink = 0, saturation = 1, ring = 0;
  State state = State::Idle;
  double time_ms = 0;
};
class Animator {
 public:
  Pose update(const Input &input);
  void reset();
 private:
  Pose previous_{}, start_{};
  State state_ = State::Idle;
  double changed_at_ = 0, last_time_ = -1;
};
// Caller supplies a 115200-byte RGB565 buffer per eye (PSRAM on the board).
// Returns false for invalid buffers, side or pose. Corners outside the disc are black.
bool render(const Pose &pose, int side, uint16_t *pixels, std::size_t count);
} // namespace pikoo::eyes
