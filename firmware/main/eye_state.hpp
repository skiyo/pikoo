#pragma once
#include "pikoo_core.hpp"
#include "pikoo_eyes.hpp"
namespace pikoo {
inline eyes::State eye_state(Session::State state) {
  // These enums deliberately have different orders. Never cast their ordinals.
  switch(state) {
    case Session::State::Idle:return eyes::State::Idle;
    case Session::State::Connecting:return eyes::State::Connecting;
    case Session::State::Listening:return eyes::State::Listening;
    case Session::State::Speaking:return eyes::State::Speaking;
    case Session::State::Thinking:return eyes::State::Thinking;
    case Session::State::Muted:return eyes::State::Muted;
    case Session::State::Offline:return eyes::State::Offline;
    case Session::State::Occupied:return eyes::State::Occupied;
    case Session::State::AuthError:return eyes::State::AuthError;
  }
  return eyes::State::Idle;
}
}
