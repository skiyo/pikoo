// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "agent_http.hpp"
#include "agent_tunnel.hpp"
#include "esp_timer.h"
#include "mbedtls/platform_util.h"
#include "pikoo_http.hpp"
#include <algorithm>
namespace pikoo {
HttpResult service_request(const HttpRequest &r, const NetworkConfig &network,
                           const std::atomic<uint64_t> &current) {
  HttpResult result{r.token, 0, {}};
  auto url = endpoint(r.url, "https");
  if (!url.valid)
    return result;
  auto transport = service_transport(network);
  if (!transport)
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
  std::string wire =
      "POST " + url.path + " HTTP/1.1\r\nHost: " + host +
      "\r\nContent-Type: application/json\r\nAccept: "
      "application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n" +
      (r.authorization.empty() ? ""
                               : "Authorization: " + r.authorization + "\r\n") +
      "Content-Length: " + std::to_string(r.body.size()) + "\r\n\r\n" + r.body;
  auto now = uint64_t(esp_timer_get_time() / 1000);
  int timeout =
      now < r.deadline ? int(std::min<uint64_t>(r.deadline - now, 15000)) : 0;
  if (current == r.token && timeout &&
      esp_transport_connect(transport, url.host.c_str(), url.port, timeout) ==
          0) {
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
      }
    }
  }
  mbedtls_platform_zeroize(wire.data(), wire.size());
  esp_transport_destroy(transport);
  return result;
}
} // namespace pikoo
