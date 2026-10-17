#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <deque>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace pikoo {
// A producer may refill a queue while it is consumed. Always return control to
// receive/cancel handling instead of draining an indefinitely nonempty stream.
template<class Pop,class Consume>
unsigned pump_bounded(unsigned limit,Pop pop,Consume consume) {
  unsigned count=0;
  while(count<limit&&pop()){consume();++count;}
  return count;
}
// Platform-neutral code shared by ESP32 and desktop fault-injection tests.
class Playback {
public:
  struct Chunk {
    std::string id;
    std::vector<int16_t> pcm;
    uint32_t epoch;
  };
  explicit Playback(size_t max_samples = 24000 * 8) : limit_(max_samples) {}
  void announce(const std::string &id) {
    if (!id.empty() && id.size() <= 128 && known_.size() < 32 && !rejected(id))
      known_.insert(id);
  }
  void reject(const std::string &id) {
    if (!id.empty() && id.size() <= 128)
      rejected_.insert(id);
  }
  bool append(const std::string &id, const int16_t *data, size_t count) {
    if (id.empty() || id.size() > 128 || !count || rejected_.count(id))
      return false;
    auto it = responses_.find(id);
    if ((it != responses_.end() && it->second.done) || count > limit_ - queued_)
      return false;
    // Bound metadata as well as PCM. The caller closes pathological sessions.
    if (it == responses_.end() && responses_.size() >= 32)
      return false;
    responses_[id].remaining += count;
    queue_.push_back({id, {data, data + count}, epoch_});
    queued_ += count;
    return true;
  }
  void done(const std::string &id) {
    auto i = responses_.find(id);
    if (i != responses_.end()) {
      i->second.done = true;
    } else {
      known_.erase(id);
      reject(id);
    }
  }
  bool take(Chunk &out,size_t initial_samples=0,uint64_t now_ms=0) {
    if (queue_.empty())
      return false;
    auto &response=responses_.at(queue_.front().id);
    if(initial_samples&&!response.started&&!response.done&&response.remaining<initial_samples) {
      if(!response.buffering){response.buffering=true;response.buffered_at=now_ms;}
      if(now_ms<response.buffered_at||now_ms-response.buffered_at<200)return false;
    }
    out = std::move(queue_.front());
    queue_.pop_front();
    queued_ -= out.pcm.size();
    return true;
  }
  bool started(const Chunk &c) {
    auto i = responses_.find(c.id);
    if (c.epoch != epoch_ || i == responses_.end() || i->second.started)
      return false;
    i->second.started = true;
    return true;
  }
  // Call only after the hardware has consumed the chunk, not when enqueued.
  void drained(const Chunk &c) { drained(c.id, c.pcm.size(), c.epoch); }
  void drained(const std::string &id, size_t samples, uint32_t epoch) {
    auto i = responses_.find(id);
    if (epoch == epoch_ && i != responses_.end())
      i->second.remaining -= std::min(i->second.remaining, samples);
  }
  std::vector<std::string> completed() {
    std::vector<std::string> ids;
    for (auto i = responses_.begin(); i != responses_.end();) {
      if (i->second.done && !i->second.remaining) {
        known_.erase(i->first);
        ids.push_back(i->first);
        rejected_.insert(i->first);
        i = responses_.erase(i);
      } else
        ++i;
    }
    return ids;
  }
  std::vector<std::string> cancel() {
    ++epoch_;
    rejected_.insert(known_.begin(), known_.end());
    known_.clear();
    std::vector<std::string> ids;
    for (const auto &p : responses_) {
      ids.push_back(p.first);
      rejected_.insert(p.first);
    }
    responses_.clear();
    queue_.clear();
    queued_ = 0;
    return ids;
  }
  void reset() {
    cancel();
    rejected_.clear();
  }
  uint32_t epoch() const { return epoch_; }
  bool busy() const { return !responses_.empty(); }
  bool rejected(const std::string &id) const { return rejected_.count(id); }
  bool exhausted() const { return rejected_.size() >= 1024; }
  size_t queued() const { return queued_; }

private:
  struct Response {
    size_t remaining = 0;
    bool done = false;
    bool started = false;
    bool buffering = false;
    uint64_t buffered_at = 0;
  };
  size_t limit_, queued_ = 0;
  uint32_t epoch_ = 0;
  std::deque<Chunk> queue_;
  std::map<std::string, Response> responses_;
  std::set<std::string> rejected_, known_;
};

// 24 -> 16 kHz rational FIR resampler. Filter at 48 kHz, 2x interpolation,
// then 3x decimation. State crosses packet boundaries; no pitch change.
class Resampler {
public:
  Resampler() {
    double sum = 0;
    for (int i = 0; i < 63; ++i) {
      const double x = i - 31, fc = 0.15;
      double h = (x == 0 ? 2 * fc : std::sin(2 * M_PI * fc * x) / (M_PI * x));
      h *= 0.42 - 0.5 * std::cos(2 * M_PI * i / 62) +
           0.08 * std::cos(4 * M_PI * i / 62);
      taps_[i] = h;
      sum += h;
    }
    for (auto &t : taps_)
      t *= 2 / sum;
  }
  void reset() {
    history_.fill(0);
    cursor_ = phase_ = 0;
  }
  std::vector<int16_t> process(const int16_t *pcm, size_t n) {
    std::vector<int16_t> out;
    out.reserve((n * 2 + 2) / 3);
    for (size_t i = 0; i < n; ++i)
      for (int up = 0; up < 2; ++up) {
        history_[cursor_] = up == 0 ? pcm[i] : 0;
        if (phase_ == 0) {
          float v = 0;
          // Half the interpolated history is zero. Select the active phase,
          // and wrap by subtraction instead of dividing inside every FIR tap.
          size_t at = (cursor_ + 63 - up) % 63;
          for (size_t k = up; k < 63; k += 2) {
            v += taps_[k] * history_[at];
            at = at >= 2 ? at - 2 : at + 61;
          }
          out.push_back(static_cast<int16_t>(std::clamp(v, -32768.f, 32767.f)));
        }
        cursor_ = (cursor_ + 1) % 63;
        phase_ = (phase_ + 1) % 3;
      }
    return out;
  }

private:
  std::array<float, 63> taps_{};
  std::array<int16_t, 63> history_{};
  size_t cursor_ = 0, phase_ = 0;
};

class Session {
public:
  enum class State {
    Idle,
    Connecting,
    Listening,
    Speaking,
    Thinking,
    Muted,
    Offline,
    Occupied,
    AuthError
  };
  State state = State::Idle;
  uint64_t last_activity = 0;
  bool ready = false;
  void wake(uint64_t now) {
    if (state == State::Muted || state == State::AuthError)
      return;
    state = State::Connecting;
    ready = false;
    last_activity = now;
  }
  void voice_ready(uint64_t now) {
    if (state == State::Connecting) {
      ready = true;
      state = State::Listening;
      last_activity = now;
    }
  }
  void mute() {
    ready = false;
    state = State::Muted;
  }
  void stop() {
    ready = false;
    state = State::Idle;
  }
  bool upload() const {
    return ready && (state == State::Listening || state == State::Speaking ||
                     state == State::Thinking);
  }
  bool idle_due(uint64_t now, bool playback) const {
    return upload() && !playback && now >= last_activity &&
           now - last_activity >= 30000;
  }
};
} // namespace pikoo
