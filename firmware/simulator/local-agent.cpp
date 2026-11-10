// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_agent.hpp"
#include "pikoo_core.hpp"
#include "pikoo_eyes.hpp"
#include <openssl/evp.h>
#include <algorithm>
#include <array>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <ctime>
#include <iostream>
#include <string>
#include <sys/resource.h>
#include <thread>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
constexpr unsigned Rate = pikoo::LiveAgent::Rate;
constexpr unsigned FrameMs = 40;
constexpr unsigned FrameSamples = Rate * FrameMs / 1000;
using namespace std::chrono_literals;
constexpr char Started[] = R"({"type":"session.started","session":{"audio":{"format":{"type":"audio/pcm","rate":16000}}}})";

std::string frame() {
  std::array<int16_t, FrameSamples> pcm;
  pcm.fill(31);
  std::string encoded(4 * ((sizeof(pcm) + 2) / 3) + 1, '\0');
  const int bytes = EVP_EncodeBlock(reinterpret_cast<unsigned char *>(encoded.data()),
    reinterpret_cast<const unsigned char *>(pcm.data()), sizeof(pcm));
  encoded.resize(bytes);
  return R"({"type":"session.output_audio.delta","delta":")" + encoded + "\"}";
}

struct Sink {
  pikoo::Playback queue;
  pikoo::Playback::Chunk chunk;
  size_t offset = 0, drained = 0, peak = 0;
  unsigned underruns = 0;
  uint64_t first = 0;
  bool working = false;
  void write(const std::string &audio) {
    assert(audio.size() % 4 == 0 && audio.size() <= 4 * ((FrameSamples * 2 + 2) / 3));
    std::array<int16_t, FrameSamples + 2> pcm{};
    int bytes = EVP_DecodeBlock(reinterpret_cast<unsigned char *>(pcm.data()),
      reinterpret_cast<const unsigned char *>(audio.data()), audio.size());
    assert(bytes > 0);
    bytes -= (audio.back() == '=') + (audio[audio.size() - 2] == '=');
    assert(bytes == FrameSamples * 2 && pcm[0] == 31);
    assert(queue.append("live", pcm.data(), bytes / 2));
    peak = std::max(peak, queue.queued());
  }
  void tick(uint64_t now) {
    unsigned samples = FrameSamples;
    while (samples) {
      if (!working) {
        if (!queue.take(chunk, queue.initial_samples(), now, 1500, true)) {
          if (first) ++underruns;
          break;
        }
        working = true;
        offset = 0;
        if (queue.started(chunk) && !first) first = now;
      }
      const auto count = std::min<size_t>(samples, chunk.pcm.size() - offset);
      offset += count;
      drained += count;
      samples -= count;
      if (offset == chunk.pcm.size()) { queue.drained(chunk); working = false; }
    }
  }
  void clear() {
    queue.cancel();
    queue.reset();
    first = 0;
    working = false;
  }
};

struct Device {
  std::string saved;
  std::vector<std::string> sent;
  Sink sink;
  bool ready = false, storage_failure = false;
  int failure = -1;
  pikoo::FamilyStore store{[&](const std::string &value) {
    if (storage_failure) return false;
    saved = value;
    return true;
  }};
  pikoo::LiveAgent agent{store, {
    [&](const std::string &s) { sent.push_back(s); return true; },
    [&](unsigned rate) { assert(sink.queue.set_sample_rate(rate)); ready = true; },
    [&](const std::string &audio) { if (ready) sink.write(audio); },
    [&](int code) { failure = code; ready = false; }
  }};
  void start(uint64_t now) {
    ready = false;
    failure = -1;
    sent.clear();
    agent.start(now, false);
  }
  void stop() {
    agent.flush_context();
    agent.reset();
    ready = false;
    sink.clear();
  }
};

std::string decision(const char *id, const char *choice) {
  return std::string(R"({"type":"decision.event","source_event_type":"session.input_transcript.delta","source_event_id":")") +
    id + R"(","event":{"type":"decision.completed","decision":{"answers":[{"name":"interaction","choice":")" +
    choice + R"("}]}}})";
}
void run_regressions() {
  Device device;
  const auto pcm = frame();
  device.start(100);
  assert(device.sent.size() == 1 && device.sent[0].find("gpt-live-1") != std::string::npos);
  device.agent.receive(pcm, 101);
  assert(!device.ready && !device.sink.queue.queued());
  device.agent.receive(Started, 102);
  assert(device.ready);
  device.agent.receive(pcm, 103);
  assert(device.sink.queue.queued() == FrameSamples);
  device.stop();
  device.agent.receive(pcm, 104);
  assert(device.sink.queue.queued() == 0);
  device.start(1000);
  device.agent.receive(Started, 1001);
  device.agent.receive(R"({"type":"session.input_transcript.delta","event_id":"tv","delta":"电视对白"})", 2000);
  device.agent.receive(decision("tv", "ignore"), 3000);
  device.agent.tick(7100);
  assert(device.store.history()->child == nullptr);
  assert(device.agent.sleep_due(61000, false));
  device.agent.receive(R"({"type":"session.input_transcript.delta","event_id":"user","delta":"问 Pikoo 的问题"})", 62000);
  device.agent.receive(R"({"type":"session.output_transcript.delta","delta":"先回答"})", 62050);
  device.agent.receive(decision("tv", "farewell"), 62100);
  device.agent.receive(decision("user", "addressed"), 62200);
  device.agent.tick(63000);
  assert(pikoo::json(device.store.history().get()).find("问 Pikoo 的问题") != std::string::npos);
  assert(pikoo::json(device.store.history().get()).find("电视对白") == std::string::npos);
  assert(!device.agent.sleep_due(67000, false));
  device.agent.receive(R"({"type":"session.input_transcript.delta","event_id":"bye","delta":"Pikoo 再见"})", 69000);
  device.agent.receive(decision("bye", "farewell"), 69300);
  device.agent.receive(pcm, 70000);
  assert(!device.agent.sleep_due(71000, false));
  assert(!device.agent.sleep_due(72000, true));
  assert(device.agent.sleep_due(72000, false));

  const char *add = R"({"group":"shopping","operation":"add","entry":"奶酪"})";
  const char *remove = R"({"group":"shopping","operation":"remove","entry":"奶酪"})";
  const char *list = R"({"group":"shopping","operation":"list"})";
  assert(device.store.call("one", "family_list", add) == R"({"ok":true})");
  auto saved = device.saved;
  device.storage_failure = true;
  assert(device.store.call("two", "family_list", remove).find("storage_failed") != std::string::npos);
  assert(device.saved == saved && device.store.call("list", "family_list", list).find("奶酪") != std::string::npos);
  Device reboot;
  assert(reboot.store.load(saved));
  assert(!reboot.store.load(saved + "garbage"));
  assert(reboot.store.call("one", "family_list", add).find("already_applied") != std::string::npos);
  assert(reboot.store.call("two", "family_list", remove) == R"({"ok":true})");
  assert(reboot.store.call("list", "family_list", list) == R"({"entries":[]})");
  assert(reboot.store.history()->child == nullptr);

  const char *created = R"({"type":"response.event","delegation_id":"d","event":{"type":"response.created","response":{"id":"r"}}})";
  const char *call = R"({"type":"response.event","delegation_id":"d","event":{"type":"response.output_item.done","response_id":"r","item":{"type":"function_call","call_id":"fresh","name":"family_list","arguments":"{\"group\":\"todo\",\"operation\":\"add\",\"entry\":\"买书\"}"}}})";
  const char *done = R"({"type":"response.event","delegation_id":"d","event":{"type":"response.completed","response":{"id":"r"}}})";
  reboot.start(10);
  reboot.agent.receive(Started, 11);
  reboot.agent.receive(created, 20);
  reboot.agent.receive(call, 21);
  reboot.agent.receive(call, 22);
  reboot.agent.receive(done, 23);
  reboot.agent.receive(done, 24);
  assert(reboot.sent.size() == 3 && reboot.saved.find("买书") != std::string::npos);
  reboot.start(30);
  reboot.agent.receive(Started, 31);
  reboot.agent.receive(created, 40);
  reboot.agent.receive(call, 41);
  reboot.agent.tick(20040);
  reboot.agent.receive(done, 20041);
  assert(reboot.sent.size() == 1);
  reboot.agent.receive(R"({"type":"error","error":{"code":"rate_limit_exceeded"}})", 20042);
  assert(reboot.failure == 429);

  reboot.stop();
  reboot.sent.clear();
  reboot.agent.start(100, false, 24000);
  assert(reboot.sent.size() == 1 && reboot.sent[0].find("24000") != std::string::npos);
  reboot.agent.receive(Started, 110);
  assert(reboot.failure == 4003);
  reboot.stop();
  reboot.agent.start(120, false, 24000);
  reboot.agent.receive(R"({"type":"session.started","session":{"audio":{"format":{"type":"audio/pcm","rate":24000}}}})", 130);
  assert(reboot.ready && reboot.sink.queue.sample_rate() == 24000);
  pikoo::LiveUpload24k converter;
  int16_t samples[] = {0, 300, 600, 900}, up[6]{};
  assert(converter.convert(samples, 2, up) == 3);
  assert(converter.convert(samples + 2, 2, up + 3) == 3);
  assert((std::vector<int16_t>(up, up + 6) == std::vector<int16_t>{0, 0, 200, 400, 600, 800}));
  assert(pikoo::connect_request("ZmFrZTp0ZXN0").find("CONNECT api.openai.com:443 ") == 0);
  assert(pikoo::connect_request("x\r\nheader: y").empty());
  assert(pikoo::connect_status("HTTP/1.1 200 Connection established\r\n\r\n") == 200);
  assert(pikoo::connect_status("HTTP/1.1 407 Proxy Authentication Required\r\n\r\n") == 407);
  assert(pikoo::connect_status("HTTP/1.1 2000 Invalid\r\n\r\n") == -1);
}

int percentile(std::vector<int> data, unsigned p) {
  std::sort(data.begin(), data.end());
  return data[(data.size() * p + 99) / 100 - 1];
}
void bench(unsigned seconds, bool realtime) {
  Device device;
  const auto pcm = frame();
  const auto raw = pikoo::text(pikoo::parse(pcm).get(), "delta");
  std::vector<int> first_pcm, first_play, core_us, baseline_us;
  const auto start = Clock::now();
  const auto cpu = std::clock();
  uint64_t clock = 1;
  std::vector<uint16_t> eyes(2 * pikoo::eyes::EyePixels);
  pikoo::eyes::Animator animator;
  uint64_t eye_checksum = 0;
  for (int i = 0; i < 100; ++i) {
    device.stop();
    device.start(clock);
    device.agent.receive(Started, clock + 5);
    first_pcm.push_back(30);
    for (uint64_t t = clock + 30; t < clock + 2030; t += FrameMs) {
      auto at = Clock::now();
      device.agent.receive(pcm, t);
      core_us.push_back(int(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - at).count()));
      device.sink.tick(t);
    }
    assert(device.ready && device.sink.first && device.sink.underruns == 0);
    first_play.push_back(int(device.sink.first - clock));
    clock += 3000;
  }
  device.stop();
  device.start(clock);
  device.agent.receive(Started, clock + 1);
  Sink baseline;
  assert(baseline.queue.set_sample_rate(Rate));
  for (uint64_t i = 0, frames = uint64_t(seconds) * 1000 / FrameMs; i < frames; ++i) {
    const auto time = clock + FrameMs * (i + 1);
    if (realtime) std::this_thread::sleep_until(start + std::chrono::milliseconds(FrameMs * (i + 1)));
    auto at = Clock::now();
    device.agent.receive(pcm, time);
    if (core_us.size() < 20000) core_us.push_back(int(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - at).count()));
    at = Clock::now();
    auto legacy = pikoo::parse(R"({"type":"audio.delta","audio":")" + raw + "\"}");
    baseline.write(pikoo::text(legacy.get(), "audio"));
    if (baseline_us.size() < 20000) baseline_us.push_back(int(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now() - at).count()));
    device.sink.tick(time);
    baseline.tick(time);
    device.agent.tick(time);
    if (i % 25 == 0) {
      const auto pose = animator.update({pikoo::eyes::State::Speaking, double(time), 17});
      for (int side = 0; side < 2; ++side)
        assert(pikoo::eyes::render_fast(pose, side, eyes.data() + side * pikoo::eyes::EyePixels,
          pikoo::eyes::EyePixels));
      eye_checksum += eyes[(i * 101) % eyes.size()];
      if (realtime && i % 1500 == 0) {
        rusage current{};
        getrusage(RUSAGE_SELF, &current);
        std::cerr << "{\"elapsed_seconds\":" << i / 25
          << ",\"underruns\":" << device.sink.underruns
          << ",\"maxrss_native_units\":" << current.ru_maxrss << "}\n";
      }
    }
  }
  assert(device.sink.underruns == 0 && baseline.underruns == 0 && eye_checksum > 0);
  rusage usage{};
  getrusage(RUSAGE_SELF, &usage);
  std::cout << "{\"reconnections\":100,\"stream_seconds\":" << seconds << ",\"real_time\":" << (realtime ? "true" : "false")
    << ",\"scripted_first_pcm_ms_p50\":" << percentile(first_pcm, 50)
    << ",\"scripted_first_pcm_ms_p95\":" << percentile(first_pcm, 95)
    << ",\"virtual_play_ms_p50\":" << percentile(first_play, 50)
    << ",\"virtual_play_ms_p95\":" << percentile(first_play, 95)
    << ",\"edge_processing_us_p95\":" << percentile(core_us, 95)
    << ",\"legacy_ingest_us_p95\":" << percentile(baseline_us, 95)
    << ",\"peak_samples\":" << device.sink.peak << ",\"underruns\":" << device.sink.underruns
    << ",\"cpu_seconds\":" << double(std::clock() - cpu) / CLOCKS_PER_SEC
    << ",\"maxrss_native_units\":" << usage.ru_maxrss << ",\"eye_checksum\":" << eye_checksum << "}\n";
}
}

namespace {
void wire() {
  Device device;
  uint64_t now = 1;
  std::string line;
  while (std::getline(std::cin, line)) {
    auto request = pikoo::parse(line);
    const auto action = pikoo::text(request.get(), "op");
    device.sent.clear();
    if (action == "connect") {
      device.stop();
      device.start(now);
    } else if (action == "close") {
      device.stop();
    } else if (action == "receive") {
      device.agent.receive(pikoo::text(request.get(), "message"), now);
    } else if (action == "drain") {
      device.sink.tick(now);
    }
    now += FrameMs;
    auto reply = pikoo::object();
    cJSON_AddBoolToObject(reply.get(), "ready", device.ready);
    cJSON_AddNumberToObject(reply.get(), "queued", device.sink.queue.queued());
    cJSON_AddNumberToObject(reply.get(), "drained", device.sink.drained);
    auto messages = cJSON_AddArrayToObject(reply.get(), "send");
    for (const auto &message : device.sent)
      cJSON_AddItemToArray(messages, cJSON_CreateString(message.c_str()));
    std::cout << pikoo::json(reply.get()) << std::endl;
  }
}
}

int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--wire") { wire(); return 0; }
  run_regressions();
  const unsigned seconds = argc > 1 ? std::stoul(argv[1]) : 15;
  if (seconds == 0) return 0;
  bench(seconds, argc > 2 && std::string(argv[2]) == "--realtime");
}
