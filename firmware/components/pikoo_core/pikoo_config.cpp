// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_config.hpp"
#include "pikoo_agent.hpp"
#include <algorithm>
#include <cctype>
#include <cstdlib>
namespace pikoo {
Endpoint endpoint(const std::string &url, const char *scheme) {
  Endpoint e;
  const std::string prefix = std::string(scheme) + "://";
  if (url.size() > 2048 || url.compare(0, prefix.size(), prefix) ||
      std::any_of(url.begin(), url.end(),
                  [](unsigned char c) { return c <= 32 || c >= 127; }) ||
      url.find('#') != std::string::npos || url.find('\\') != std::string::npos)
    return e;
  auto end = url.find_first_of("/?", prefix.size());
  auto authority = url.substr(prefix.size(), end - prefix.size());
  if (authority.empty() || authority.find('@') != std::string::npos)
    return e;
  size_t port_at = std::string::npos;
  if (authority[0] == '[') {
    auto bracket = authority.find(']');
    if (bracket == std::string::npos || bracket < 3)
      return e;
    e.host = authority.substr(1, bracket - 1);
    if (e.host.find(':') == std::string::npos ||
        std::any_of(e.host.begin(), e.host.end(), [](unsigned char c) {
          return !std::isxdigit(c) && c != ':' && c != '.';
        }))
      return Endpoint{};
    if (bracket + 1 < authority.size()) {
      if (authority[bracket + 1] != ':')
        return Endpoint{};
      port_at = bracket + 1;
    }
  } else {
    port_at = authority.find(':');
    e.host = authority.substr(0, port_at);
    if (e.host.empty() || e.host.size() > 253 || e.host.front() == '.' ||
        e.host.back() == '.' ||
        std::any_of(e.host.begin(), e.host.end(), [](unsigned char c) {
          return !std::isalnum(c) && c != '.' && c != '-';
        }))
      return Endpoint{};
  }
  if (port_at != std::string::npos) {
    auto port = authority.substr(port_at + 1);
    if (port.empty() || port.size() > 5 ||
        port.find_first_not_of("0123456789") != std::string::npos)
      return Endpoint{};
    unsigned value = unsigned(std::strtoul(port.c_str(), nullptr, 10));
    if (!value || value > 65535)
      return Endpoint{};
    e.port = uint16_t(value);
  }
  e.path = end == std::string::npos ? "/" : url.substr(end);
  if (e.path[0] == '?')
    e.path = "/" + e.path;
  std::transform(e.host.begin(), e.host.end(), e.host.begin(),
                 [](unsigned char c) { return std::tolower(c); });
  e.valid = true;
  return e;
}
bool decode_config(const std::string &payload, AgentConfig &out,
                   std::string &error) {
  error.clear();
  auto reject = [&](const char *code) {
    error = code;
    return false;
  };
  if (payload.find("\\u0000") != std::string::npos)
    return reject("nul_character");
  if (payload.size() > AgentConfig::Limit)
    return reject("configuration_too_large");
  auto o = parse(payload);
  auto version = field(o.get(), "version");
  if (!cJSON_IsNumber(version) || version->valuedouble != 1)
    return reject("configuration_version");
  for (const char *section :
       {"wifi", "agent", "live", "llm", "search", "network"}) {
    auto v = field(o.get(), section);
    if (v && !cJSON_IsObject(v))
      return reject("configuration_section");
    for (const char *key :
         {"ssid", "password", "name", "language", "instructions", "protocol",
          "url", "api_key", "model", "voice", "extract_url", "proxy_url",
          "proxy_basic"}) {
      auto value = field(v, key);
      if (value && !cJSON_IsString(value))
        return reject("configuration_string");
    }
  }
  AgentConfig c;
  auto wifi = field(o.get(), "wifi");
  c.ssid = text(wifi, "ssid");
  c.password = text(wifi, "password");
  if (!cJSON_IsString(field(wifi, "password")) || c.ssid.empty() ||
      c.ssid.size() > 32 || c.password.size() > 63 ||
      (!c.password.empty() && c.password.size() < 8))
    return reject("wifi_settings");
  auto a = field(o.get(), "agent");
  if (a) {
    c.name = text(a, "name");
    c.language = text(a, "language");
    c.instructions = text(a, "instructions");
  }
  if (c.name.empty() || c.name.size() > 64 || c.language.empty() ||
      c.language.size() > 32 || c.instructions.size() > 2048)
    return reject("agent_settings");
  auto read = [&](const char *key, ServiceConfig &s) {
    auto v = field(o.get(), key);
    s = {text(v, "protocol"), text(v, "url"), text(v, "api_key"),
         text(v, "model")};
  };
  read("live", c.live);
  read("llm", c.llm);
  read("search", c.search);
  const auto rate = field(field(o.get(), "live"), "audio_rate");
  if (rate) {
    if (!cJSON_IsNumber(rate) ||
        (rate->valuedouble != 16000 && rate->valuedouble != 24000))
      return reject("audio_rate");
    c.audio_rate = unsigned(rate->valueint);
  }
  auto voice = field(field(o.get(), "live"), "voice");
  if (voice)
    c.voice = text(field(o.get(), "live"), "voice");
  if (c.voice.empty() || c.voice.size() > 64)
    return reject("voice");
  if (c.live.protocol != "openai_live")
    return reject("live_protocol");
  if (c.llm.protocol != "openai_responses" &&
      c.llm.protocol != "openai_chat_completions")
    return reject("llm_protocol");
  auto enabled = field(field(o.get(), "search"), "enabled");
  if (enabled && !cJSON_IsBool(enabled))
    return reject("search_enabled");
  c.search_enabled = cJSON_IsTrue(enabled);
  auto service_ok = [](const ServiceConfig &s, const char *scheme, bool model) {
    return endpoint(s.url, scheme).valid &&
           (s.api_key.empty() || safe_header(s.api_key)) &&
           (!model || (!s.model.empty() && s.model.size() <= 128));
  };
  if (!service_ok(c.live, "wss", true))
    return reject("live_settings");
  if (!service_ok(c.llm, "https", true))
    return reject("llm_settings");
  if (c.search_enabled) {
    if (c.search.protocol != "tavily" &&
        c.search.protocol != "openai_responses")
      return reject("search_protocol");
    if (!service_ok(c.search, "https", c.search.protocol == "openai_responses"))
      return reject("search_settings");
    c.extract_url = text(field(o.get(), "search"), "extract_url");
    if (!c.extract_url.empty() && (c.search.protocol != "tavily" ||
                                   !endpoint(c.extract_url, "https").valid))
      return reject("extract_settings");
    // Extraction uses the search credential: require its exact origin.
    if (!c.extract_url.empty()) {
      auto s = endpoint(c.search.url, "https"),
           e = endpoint(c.extract_url, "https");
      if (s.host != e.host || s.port != e.port)
        return reject("extract_origin");
    }
  }
  auto net = field(o.get(), "network");
  c.network.proxy_url = text(net, "proxy_url");
  c.network.proxy_basic = text(net, "proxy_basic");
  if ((!c.network.proxy_url.empty() &&
       !endpoint(c.network.proxy_url, "https").valid) ||
      (!c.network.proxy_basic.empty() &&
       (!safe_header(c.network.proxy_basic) || c.network.proxy_url.empty())))
    return reject("proxy_settings");
  if (!c.network.proxy_url.empty() &&
      endpoint(c.network.proxy_url, "https").path != "/")
    return reject("proxy_path");
  out = std::move(c);
  return true;
}
std::string connect_request(const std::string &host, uint16_t port,
                            const std::string &basic) {
  auto target = endpoint(
      "https://" +
          (host.find(':') == std::string::npos ? host : "[" + host + "]") +
          ":" + std::to_string(port),
      "https");
  if (!target.valid || (!basic.empty() && !safe_header(basic)))
    return {};
  const auto authority =
      (host.find(':') == std::string::npos ? host : "[" + host + "]") + ":" +
      std::to_string(port);
  return "CONNECT " + authority + " HTTP/1.1\r\nHost: " + authority + "\r\n" +
         (basic.empty() ? "" : "Proxy-Authorization: Basic " + basic + "\r\n") +
         "\r\n";
}
} // namespace pikoo
