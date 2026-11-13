// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include <string>
namespace pikoo {
// Bounded HTTP/1.x response decoder shared by device and fault tests.
class HttpResponse {
public:
  static constexpr size_t BodyLimit = 64 * 1024, HeaderLimit = 8192;
  bool feed(const char *data, size_t size);
  bool eof();
  bool done() const { return done_; }
  int status() const { return failed_ ? 0 : status_; }
  const std::string &body() const { return body_; }
  bool reusable() const {
    return done_ && !failed_ && keep_alive_ && (has_length_ || chunked_);
  }

private:
  bool consume();
  bool fail() {
    failed_ = true;
    return false;
  }
  std::string pending_, body_;
  int status_ = 0;
  size_t length_ = 0, chunk_ = 0, wire_ = 0;
  bool headers_ = false, chunked_ = false, has_length_ = false,
       need_size_ = true, trailers_ = false, done_ = false, failed_ = false,
       keep_alive_ = false;
};
} // namespace pikoo
