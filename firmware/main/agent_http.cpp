// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "agent_http.hpp"
#include "agent_tunnel.hpp"
#include "esp_timer.h"
#include "esp_log.h"
#include "mbedtls/platform_util.h"
#include "pikoo_http.hpp"
#include <algorithm>
namespace pikoo {
namespace {
// One connection, scoped to a delegation and exact HTTPS/proxy origins.
// Authorization is always rebuilt from the current request; it is not cached.
struct Connection {
  esp_transport_handle_t transport = nullptr;
  std::string origin, proxy_url, proxy_basic;
  uint64_t scope = 0, expires = 0;
  void reset() {
    if (transport)
      esp_transport_destroy(transport);
    transport = nullptr;
    origin.clear();
    proxy_url.clear();
    mbedtls_platform_zeroize(proxy_basic.data(), proxy_basic.size());
    proxy_basic.clear();
    scope = expires = 0;
  }
  ~Connection() { reset(); }
} connection;
} // namespace
void service_request_idle(const std::atomic<uint64_t> &current) {
  if (connection.transport &&
      (connection.scope != current ||
       uint64_t(esp_timer_get_time() / 1000) >= connection.expires))
    connection.reset();
}
HttpResult service_request(const HttpRequest &r, const NetworkConfig &network,
                           const std::atomic<uint64_t> &current,
                           const std::atomic<uint64_t> &scope) {
  HttpResult result{r.token, 0, {}};
  auto url = endpoint(r.url, "https");
  if (!url.valid)
    return result;
  auto remaining = [&] {
    auto now = uint64_t(esp_timer_get_time() / 1000);
    return now < r.deadline && current == r.token
               ? int(std::min<uint64_t>(r.deadline - now, 1000))
               : 0;
  };
  auto host =
      url.host.find(':') == std::string::npos ? url.host : "[" + url.host + "]";
  if (url.port != 443)
    host += ":" + std::to_string(url.port);
  service_request_idle(scope);
  if (connection.transport &&
      (connection.scope != r.scope || connection.origin != host ||
       connection.proxy_url != network.proxy_url ||
       connection.proxy_basic != network.proxy_basic ||
       esp_transport_poll_read(connection.transport, 0) != 0))
    connection.reset();
  const bool reused = connection.transport;
  ESP_LOGI("pikoo", "backend connection reused=%d", int(reused));
  auto transport = reused ? connection.transport : service_transport(network);
  if (!transport)
    return result;
  bool reusable = false;
  std::string wire =
      "POST " + url.path + " HTTP/1.1\r\nHost: " + host +
      "\r\nContent-Type: application/json\r\nAccept: "
      "application/json\r\nAccept-Encoding: identity\r\nConnection: keep-alive\r\n" +
      (r.authorization.empty() ? ""
                               : "Authorization: " + r.authorization + "\r\n") +
      "Content-Length: " + std::to_string(r.body.size()) + "\r\n\r\n" + r.body;
  auto now = uint64_t(esp_timer_get_time() / 1000);
  int timeout =
      now < r.deadline ? int(std::min<uint64_t>(r.deadline - now, 15000)) : 0;
  if (current == r.token && timeout &&
      (reused || esp_transport_connect(transport, url.host.c_str(), url.port,
                                       timeout) == 0)) {
    size_t sent = 0;
    while (sent < wire.size() && remaining()) {
      int count = esp_transport_write(
          transport, wire.data() + sent,
          std::min<size_t>(4096, wire.size() - sent), remaining());
      if (count <= 0)
        break;
      sent += count;
    }
    if (sent == wire.size()) {
      HttpResponse response;
      char buffer[2048];
      bool valid = true;
      while (!response.done() && remaining()) {
        int count =
            esp_transport_read(transport, buffer, sizeof(buffer), remaining());
        if (count == ERR_TCP_TRANSPORT_CONNECTION_CLOSED_BY_FIN) {
          valid = response.eof();
          break;
        }
        if (count < 0) {
          valid = false;
          break;
        }
        if (count && !response.feed(buffer, count)) {
          valid = false;
          break;
        }
      }
      if (valid && response.done() && current == r.token) {
        result.status = response.status();
        result.body = response.body();
        reusable = response.reusable();
      }
    }
  }
  mbedtls_platform_zeroize(wire.data(), wire.size());
  if (reusable && current == r.token) {
    connection.transport = transport;
    connection.origin = host;
    connection.proxy_url = network.proxy_url;
    connection.proxy_basic = network.proxy_basic;
    connection.scope = r.scope;
    connection.expires = uint64_t(esp_timer_get_time() / 1000) + 15000;
  } else if (reused) {
    connection.reset();
  } else {
    esp_transport_destroy(transport);
  }
  return result;
}
} // namespace pikoo
