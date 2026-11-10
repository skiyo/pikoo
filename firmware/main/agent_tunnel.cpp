// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "agent_tunnel.hpp"
#include "pikoo_agent.hpp"

#include "esp_crt_bundle.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_transport_internal.h"
#include "lwip/netdb.h"
#include "lwip/sockets.h"
#include "lwip/tcp.h"
#include "mbedtls/net_sockets.h"
#include "mbedtls/platform_util.h"
#include "mbedtls/ssl.h"
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <new>
#include <utility>

namespace pikoo {
namespace {
constexpr char Destination[] = "api.openai.com";
constexpr int Invalid = -1;
constexpr int MaxWaitMs = 15000;

int remaining(int64_t deadline) {
  return int(std::clamp<int64_t>((deadline - esp_timer_get_time() + 999) / 1000, 0, MaxWaitMs));
}

struct Layer {
  mbedtls_ssl_context ssl;
  mbedtls_ssl_config config;
  Layer() { mbedtls_ssl_init(&ssl); mbedtls_ssl_config_init(&config); }
  ~Layer() { free(); }
  void free() { mbedtls_ssl_free(&ssl); mbedtls_ssl_config_free(&config); }
  bool init(const char *name) {
    if (mbedtls_ssl_config_defaults(&config, MBEDTLS_SSL_IS_CLIENT, MBEDTLS_SSL_TRANSPORT_STREAM,
                                    MBEDTLS_SSL_PRESET_DEFAULT)) return false;
    mbedtls_ssl_conf_rng(&config, [](void *, unsigned char *buf, size_t size) {
      esp_fill_random(buf, size);
      return 0;
    }, nullptr);
    mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_REQUIRED);
    return esp_crt_bundle_attach(&config) == ESP_OK && !mbedtls_ssl_setup(&ssl, &config) &&
      !mbedtls_ssl_set_hostname(&ssl, name);
  }
};

struct Tunnel {
  std::string host;
  std::string basic;
  uint16_t port;
  std::atomic<int> fd{Invalid};
  std::atomic<int> status{0};
  std::atomic<bool> aborted{false};
  std::mutex io;
  std::mutex socket_mutex;
  Layer proxy, upstream;

  Tunnel(std::string host, uint16_t port, std::string basic)
    : host(std::move(host)), basic(std::move(basic)), port(port) {}
  ~Tunnel() { close_socket(); mbedtls_platform_zeroize(basic.data(), basic.size()); }
  int wait(bool write, int timeout) const {
    const int socket = fd.load();
    if (socket < 0 || socket >= FD_SETSIZE || aborted) return -1;
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(socket, &fds);
    timeval tv{timeout / 1000, (timeout % 1000) * 1000};
    return select(socket + 1, write ? nullptr : &fds, write ? &fds : nullptr, nullptr, &tv);
  }
  void close_socket() {
    std::lock_guard<std::mutex> lock(socket_mutex);
    const int socket = fd.exchange(Invalid);
    if (socket != Invalid) ::close(socket);
  }
  void abort() {
    std::lock_guard<std::mutex> lock(socket_mutex);
    aborted = true;
    const int socket = fd.load();
    if (socket != Invalid) shutdown(socket, SHUT_RDWR);
  }
  bool tcp(int64_t deadline) {
    addrinfo hints{}, *list = nullptr;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &list)) return false;
    bool connected = false;
    for (auto addr = list; addr && !aborted && remaining(deadline); addr = addr->ai_next) {
      const int socket = ::socket(addr->ai_family, addr->ai_socktype, addr->ai_protocol);
      if (socket < 0) continue;
      { std::lock_guard<std::mutex> lock(socket_mutex); fd = socket; }
      int enabled = 1;
      setsockopt(socket, IPPROTO_TCP, TCP_NODELAY, &enabled, sizeof(enabled));
      if (!aborted && fcntl(socket, F_SETFL, O_NONBLOCK) == 0 &&
          (::connect(socket, addr->ai_addr, addr->ai_addrlen) == 0 ||
           (errno == EINPROGRESS && wait(true, remaining(deadline)) > 0))) {
        int error = 0;
        socklen_t length = sizeof(error);
        connected = getsockopt(socket, SOL_SOCKET, SO_ERROR, &error, &length) == 0 && error == 0;
      }
      if (connected) break;
      close_socket();
    }
    freeaddrinfo(list);
    return connected;
  }

  template<typename Operation>
  int perform(int64_t deadline, Operation op, bool retry = true) {
    while (!aborted) {
      int result;
      { std::lock_guard<std::mutex> lock(io); result = op(); }
      if (result != MBEDTLS_ERR_SSL_WANT_READ && result != MBEDTLS_ERR_SSL_WANT_WRITE) return result;
      const int timeout = remaining(deadline);
      if (!retry || !timeout) return 0;
      const int ready = wait(result == MBEDTLS_ERR_SSL_WANT_WRITE, timeout);
      if (ready <= 0) return ready;
    }
    return -1;
  }

  bool handshake(Layer &layer, int64_t deadline) {
    bool complete = false;
    const int result = perform(deadline, [&] {
      const int error = mbedtls_ssl_handshake(&layer.ssl);
      complete = !error;
      return error;
    });
    return !result && complete && mbedtls_ssl_get_verify_result(&layer.ssl) == 0;
  }

  bool connect(int timeout) {
    const int64_t deadline = esp_timer_get_time() + int64_t(std::clamp(timeout, 1, MaxWaitMs)) * 1000;
    const auto started = esp_timer_get_time();
    if (!tcp(deadline) || !proxy.init(host.c_str())) return false;
    const auto tcp_ready = esp_timer_get_time();
    mbedtls_ssl_set_bio(&proxy.ssl, this,
      [](void *context, const unsigned char *bytes, size_t size) -> int {
        const auto count = ::send(static_cast<Tunnel *>(context)->fd, bytes, size, 0);
        return count >= 0 ? count : (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
          ? MBEDTLS_ERR_SSL_WANT_WRITE : MBEDTLS_ERR_NET_SEND_FAILED;
      },
      [](void *context, unsigned char *bytes, size_t size) -> int {
        const auto count = ::recv(static_cast<Tunnel *>(context)->fd, bytes, size, 0);
        return count >= 0 ? count : (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
          ? MBEDTLS_ERR_SSL_WANT_READ : MBEDTLS_ERR_NET_RECV_FAILED;
      }, nullptr);
    if (!handshake(proxy, deadline)) return false;
    const auto proxy_ready = esp_timer_get_time();
    auto request = connect_request(basic);
    size_t sent = 0;
    while (sent < request.size()) {
      const int count = perform(deadline, [&] {
        return mbedtls_ssl_write(&proxy.ssl, reinterpret_cast<const unsigned char *>(request.data() + sent),
                                 request.size() - sent);
      });
      if (count <= 0) break;
      sent += count;
    }
    mbedtls_platform_zeroize(request.data(), request.size());
    if (sent != request.size() || !sent) return false;
    std::string headers;
    while (headers.size() < 8192 && headers.compare(headers.size() < 4 ? 0 : headers.size() - 4, 4, "\r\n\r\n")) {
      unsigned char byte;
      if (perform(deadline, [&] { return mbedtls_ssl_read(&proxy.ssl, &byte, 1); }) != 1) return false;
      headers.push_back(char(byte));
    }
    status = connect_status(headers);
    if (status != 200 || !upstream.init(Destination)) return false;
    const auto tunnel_ready = esp_timer_get_time();
    mbedtls_ssl_set_bio(&upstream.ssl, this,
      [](void *context, const unsigned char *bytes, size_t size) {
        return mbedtls_ssl_write(&static_cast<Tunnel *>(context)->proxy.ssl, bytes, size);
      },
      [](void *context, unsigned char *bytes, size_t size) {
        return mbedtls_ssl_read(&static_cast<Tunnel *>(context)->proxy.ssl, bytes, size);
      }, nullptr);
    if (!handshake(upstream, deadline)) return false;
    ESP_LOGI("pikoo", "tunnel tcp_ms=%lld proxy_tls_ms=%lld connect_ms=%lld openai_tls_ms=%lld "
             "heap_internal_min=%u heap_internal_largest=%u",
             (tcp_ready - started) / 1000, (proxy_ready - tcp_ready) / 1000,
             (tunnel_ready - proxy_ready) / 1000, (esp_timer_get_time() - tunnel_ready) / 1000,
             unsigned(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL)),
             unsigned(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)));
    return true;
  }

  int poll(int timeout) {
    {
      std::lock_guard<std::mutex> lock(io);
      if (mbedtls_ssl_check_pending(&upstream.ssl) || mbedtls_ssl_check_pending(&proxy.ssl)) return 1;
    }
    return wait(false, std::clamp(timeout, 0, MaxWaitMs));
  }
};

Tunnel &context(esp_transport_handle_t t) {
  return *static_cast<Tunnel *>(esp_transport_get_context_data(t));
}
}

esp_transport_handle_t openai_tunnel(const std::string &host, uint16_t port, const std::string &basic) {
  if (host.empty() || !port || !safe_header(basic)) return nullptr;
  auto state = new (std::nothrow) Tunnel(host, port, basic);
  if (!state) return nullptr;
  auto t = esp_transport_init();
  if (!t) { delete state; return nullptr; }
  esp_transport_set_context_data(t, state);
  esp_transport_set_func(t,
    [](esp_transport_handle_t handle, const char *host, int port, int timeout) {
      auto &s = context(handle);
      return port == 443 && !strcmp(host, Destination) && s.connect(timeout) ? 0 : -1;
    },
    [](esp_transport_handle_t handle, char *out, int size, int timeout) {
      auto &s = context(handle);
      bool eof = false;
      const auto result = s.perform(esp_timer_get_time() + int64_t(std::clamp(timeout, 0, MaxWaitMs)) * 1000, [&] {
        const auto count = mbedtls_ssl_read(&s.upstream.ssl, reinterpret_cast<unsigned char *>(out), size);
        eof = count == 0 || count == MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY;
        return count;
      });
      return eof ? int(ERR_TCP_TRANSPORT_CONNECTION_CLOSED_BY_FIN) : result;
    },
    [](esp_transport_handle_t handle, const char *data, int size, int timeout) {
      auto &s = context(handle);
      return s.perform(esp_timer_get_time() + int64_t(std::clamp(timeout, 0, MaxWaitMs)) * 1000, [&] {
        return mbedtls_ssl_write(&s.upstream.ssl, reinterpret_cast<const unsigned char *>(data), size);
      });
    },
    [](esp_transport_handle_t handle) { context(handle).close_socket(); return 0; },
    [](esp_transport_handle_t handle, int timeout) { return context(handle).poll(timeout); },
    [](esp_transport_handle_t handle, int timeout) {
      return context(handle).wait(true, std::clamp(timeout, 0, MaxWaitMs));
    },
    [](esp_transport_handle_t handle) { delete &context(handle); return 0; });
  // The pinned IDF WebSocket close handler polls this socket after a peer close.
  t->_get_socket = [](esp_transport_handle_t handle) { return context(handle).fd.load(); };
  esp_transport_set_parent_transport_func(t, [](esp_transport_handle_t handle) { return handle; });
  esp_transport_set_default_port(t, 443);
  return t;
}

int tunnel_status(esp_transport_handle_t t) { return t ? context(t).status.load() : 0; }
void abort_tunnel(esp_transport_handle_t t) { if (t) context(t).abort(); }
}
