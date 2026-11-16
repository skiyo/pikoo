#include "../main/agent_http.hpp"
#include "../main/agent_tunnel.hpp"
#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>
struct MockTransport {
  int attempt;
};
namespace {
int attempts = 0, mode = 0;
int64_t clock_us = 1000000;
std::atomic<uint64_t> token{1}, scope{1};
std::vector<std::string> wires;
} // namespace
int64_t esp_timer_get_time() { return clock_us; }
int esp_transport_destroy(esp_transport_handle_t t) {
  delete t;
  return 0;
}
int esp_transport_poll_read(esp_transport_handle_t, int) { return 0; }
int esp_transport_connect(esp_transport_handle_t, const char *, int, int) {
  return 0;
}
int esp_transport_write(esp_transport_handle_t, const char *p, int n, int) {
  wires.emplace_back(p, n);
  return n;
}
int esp_transport_read(esp_transport_handle_t t, char *p, int n, int) {
  if (mode == 2) {
    ++token;
    return -1;
  }
  if (mode == 3) {
    clock_us = 31000000;
    return -1;
  }
  if (mode == 4 || (mode == 0 && t->attempt == 1))
    return -1;
  const char *response = mode == 1 ? "HTTP/1.1 503 Busy\r\nContent-Length: "
                                     "2\r\nConnection: close\r\n\r\n{}"
                                   : "HTTP/1.1 200 OK\r\nContent-Length: "
                                     "2\r\nConnection: close\r\n\r\n{}";
  assert(int(std::strlen(response)) <= n);
  std::memcpy(p, response, std::strlen(response));
  return std::strlen(response);
}
namespace pikoo {
esp_transport_handle_t service_transport(const NetworkConfig &) {
  return new MockTransport{++attempts};
}
} // namespace pikoo
int main() {
  pikoo::HttpRequest r{
      1,    30000, "https://model.example.com/v1/responses", "Bearer TEST_ONLY",
      "{}", 1};
  for (mode = 0; mode < 5; ++mode) {
    attempts = 0;
    wires.clear();
    clock_us = 1000000;
    token = 1;
    auto result = pikoo::service_request(r, {}, token, scope);
    if (mode == 0) {
      assert(result.status == 200 && attempts == 2);
      assert(wires.size() == 2 && wires[0] == wires[1]);
    }
    if (mode == 1)
      assert(result.status == 503 && attempts == 1);
    if (mode == 2 || mode == 3)
      assert(result.status == 0 && attempts == 1);
    if (mode == 4)
      assert(result.status == 0 && attempts == 2);
    ++scope;
    pikoo::service_request_idle(scope);
  }
  std::cout << "Inference transport retry, same request, cancellation, "
               "deadline and HTTP error checks passed\n";
}
