// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include <cstdint>
#include <string>
namespace pikoo {
struct Endpoint {
  std::string host, path;
  uint16_t port = 443;
  bool valid = false;
};
Endpoint endpoint(const std::string &url, const char *scheme);
struct ServiceConfig {
  std::string protocol, url, api_key, model;
  std::string authorization() const {
    return api_key.empty() ? "" : "Bearer " + api_key;
  }
};
struct NetworkConfig {
  std::string proxy_url, proxy_basic;
};
struct AgentConfig {
  static constexpr size_t Limit = 16384;
  std::string ssid, password;
  std::string name = "Pikoo", language = "en", instructions;
  ServiceConfig live, llm, search;
  std::string voice = "marin", extract_url;
  unsigned audio_rate = 16000;
  bool search_enabled = false;
  NetworkConfig network;
};
bool decode_config(const std::string &payload, AgentConfig &out,
                   std::string &error);
std::string connect_request(const std::string &host, uint16_t port,
                            const std::string &proxy_basic);
} // namespace pikoo
