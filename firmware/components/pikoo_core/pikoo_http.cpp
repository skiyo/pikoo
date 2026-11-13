// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_http.hpp"
#include <algorithm>
#include <cctype>
#include <cstdlib>
namespace pikoo {
bool HttpResponse::feed(const char *p, size_t n) {
  if (failed_ || done_ || n > BodyLimit + HeaderLimit - wire_)
    return fail();
  wire_ += n;
  pending_.append(p, n);
  return consume();
}
bool HttpResponse::consume() {
  if (!headers_) {
    auto end = pending_.find("\r\n\r\n");
    if (end == std::string::npos)
      return pending_.size() <= HeaderLimit ? true : fail();
    if (end + 4 > HeaderLimit || pending_.size() < 12 ||
        (pending_.compare(0, 9, "HTTP/1.1 ") &&
         pending_.compare(0, 9, "HTTP/1.0 ")))
      return fail();
    if (pending_.find_first_not_of("0123456789", 9) < 12 || pending_[12] != ' ')
      return fail();
    status_ = std::atoi(pending_.substr(9, 3).c_str());
    if (status_ < 200 || status_ > 599)
      return fail();
    auto pos = pending_.find("\r\n") + 2;
    while (pos < end) {
      auto next = pending_.find("\r\n", pos);
      auto line = pending_.substr(pos, next - pos);
      auto colon = line.find(':');
      if (colon == std::string::npos)
        return fail();
      auto name = line.substr(0, colon), value = line.substr(colon + 1);
      std::transform(name.begin(), name.end(), name.begin(),
                     [](unsigned char c) { return std::tolower(c); });
      while (!value.empty() && value.front() == ' ')
        value.erase(0, 1);
      while (!value.empty() && value.back() == ' ')
        value.pop_back();
      if (name == "content-length") {
        if (has_length_ || value.empty() ||
            value.find_first_not_of("0123456789") != std::string::npos ||
            value.size() > 8)
          return fail();
        length_ = std::strtoul(value.c_str(), nullptr, 10);
        has_length_ = true;
        if (length_ > BodyLimit)
          return fail();
      }
      if (name == "transfer-encoding") {
        if (chunked_)
          return fail();
        std::transform(value.begin(), value.end(), value.begin(),
                       [](unsigned char c) { return std::tolower(c); });
        if (value != "chunked")
          return fail();
        chunked_ = true;
      }
      if (name == "content-encoding" && value != "identity")
        return fail();
      pos = next + 2;
    }
    if (chunked_ && has_length_)
      return fail();
    pending_.erase(0, end + 4);
    headers_ = true;
  }
  if (chunked_) {
    while (true) {
      if (trailers_) {
        if (pending_.size() < 2)
          return true;
        if (pending_ != "\r\n")
          return fail();
        pending_.clear();
        done_ = true;
        return true;
      }
      if (need_size_) {
        auto end = pending_.find("\r\n");
        if (end == std::string::npos)
          return pending_.size() <= 32 ? true : fail();
        auto number = pending_.substr(0, end);
        auto ext = number.find(';');
        if (ext != std::string::npos)
          number.resize(ext);
        if (number.empty() || number.size() > 8 ||
            number.find_first_not_of("0123456789abcdefABCDEF") !=
                std::string::npos)
          return fail();
        chunk_ = std::strtoul(number.c_str(), nullptr, 16);
        if (chunk_ > BodyLimit - body_.size())
          return fail();
        pending_.erase(0, end + 2);
        need_size_ = false;
        if (!chunk_) {
          trailers_ = true;
          continue;
        }
      }
      if (pending_.size() < chunk_ + 2)
        return true;
      if (pending_.compare(chunk_, 2, "\r\n"))
        return fail();
      body_.append(pending_, 0, chunk_);
      pending_.erase(0, chunk_ + 2);
      need_size_ = true;
    }
  }
  if (pending_.size() > BodyLimit - body_.size())
    return fail();
  body_ += pending_;
  pending_.clear();
  if (has_length_) {
    if (body_.size() > length_)
      return fail();
    done_ = body_.size() == length_;
  }
  return true;
}
bool HttpResponse::eof() {
  if (failed_ || !headers_ || (chunked_ && !done_) ||
      (has_length_ && body_.size() != length_))
    return fail();
  done_ = true;
  return true;
}
} // namespace pikoo
