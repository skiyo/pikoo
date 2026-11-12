// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once

#include "cJSON.h"

#include <cstdint>
#include <functional>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace pikoo {
using Json = std::unique_ptr<cJSON, decltype(&cJSON_Delete)>;
Json object();
Json parse(const std::string &text);
std::string json(const cJSON *value);
std::string text(const cJSON *value, const char *key);
const cJSON *field(const cJSON *value, const char *key);

class FamilyStore {
public:
  using Commit = std::function<bool(const std::string &)>;
  static constexpr size_t Capacity = 24 * 1024;
  explicit FamilyStore(Commit commit);
  bool load(const std::string &snapshot);
  std::string snapshot() const;
  std::string call(const std::string &id, const std::string &name, const std::string &arguments);
  bool remember_turn(const std::string &role, const std::string &content, bool append = false);
  bool clear_context();
  bool flush_history();
  Json history() const;

private:
  bool save(Json next);
  Json data_;
  Commit commit_;
  bool history_dirty_ = false;
};

class LiveAgent {
public:
  struct Output {
    std::function<bool(const std::string &)> send;
    std::function<void(unsigned)> ready;
    std::function<void(const std::string &)> audio;
    std::function<void(int)> failed;
    std::function<void(const char *)> diagnostic = [](const char *) {};
  };

  LiveAgent(FamilyStore &store, Output output);
  void start(uint64_t now, bool greet, unsigned rate = Rate);
  void receive(const std::string &message, uint64_t now);
  void tick(uint64_t now);
  bool sleep_due(uint64_t now, bool playing) const;
  void reset();
  void flush_context();
  static constexpr size_t MessageLimit = 64 * 1024;
  static constexpr unsigned Rate = 16000;

private:
  void send(Json event);
  void record_reply(const cJSON *message, uint64_t now);
  void flush_turn();
  void delegated(const cJSON *message, uint64_t now);
  void classify(const cJSON *message, uint64_t now);
  FamilyStore &store_;
  Output output_;
  struct Call { std::string id, name, arguments; };
  struct Batch { std::string id, response; uint64_t since; std::vector<Call> calls; };
  std::vector<Batch> batches_;
  std::set<std::string> event_types_;
  struct Input { std::string id, fragment; uint64_t at; };
  std::vector<Input> inputs_;
  std::string reply_;
  uint64_t effective_ = 0, turn_at_ = 0, farewell_at_ = 0, audio_at_ = 0;
  uint64_t serial_ = 0, expires_at_ = 0, reply_end_ = 0;
  unsigned rate_ = Rate;
  bool greeting_ = false, ready_ = false;
  bool reply_continuation_ = false;
};

// Convert complete pairs of 16 kHz microphone samples to 24 kHz. Keep the
// fractional position across packets without introducing an extra full packet.
class LiveUpload24k {
public:
  void reset() { have_previous_ = false; }
  size_t convert(const int16_t *input, size_t count, int16_t *out);
private:
  int16_t previous_ = 0;
  bool have_previous_ = false;
};

bool safe_header(const std::string &value);
std::string connect_request(const std::string &proxy_basic);
int connect_status(const std::string &headers);
}
