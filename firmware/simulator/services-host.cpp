// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
// JSON-lines host driver for the actual C++ service adapters. No audio devices.
#include "pikoo_backend.hpp"
#include "pikoo_http.hpp"
#include <iostream>
namespace {
std::vector<pikoo::HttpRequest> requests;
std::vector<std::string> replies, sent;
std::string saved;
pikoo::FamilyStore store([](const std::string &s) {
  saved = s;
  return true;
});
pikoo::BackendAgent *backend_ptr = nullptr;
pikoo::LiveAgent
    live(store, {[](const std::string &s) {
                   sent.push_back(s);
                   return true;
                 },
                 [](unsigned) {}, [](const std::string &) {}, [](int) {},
                 [](const char *) {}, [] {}, [] {}, [] {},
                 [](const std::string &id, const std::string &history,
                    uint64_t now) { backend_ptr->start(id, history, now); },
                 [] {
                   if (backend_ptr)
                     backend_ptr->cancel();
                 }});
pikoo::BackendAgent backend(
    store, [](pikoo::HttpRequest r) { requests.push_back(std::move(r)); },
    [](const std::string &id, const std::string &value) {
      replies.push_back(value);
      live.result(id, value);
    });
} // namespace
int main() {
  backend_ptr = &backend;
  std::string line;
  pikoo::HttpResponse http;
  while (std::getline(std::cin, line)) {
    auto q = pikoo::parse(line);
    if (!q) {
      std::cout << "{\"error\":\"invalid_json\"}" << std::endl;
      continue;
    }
    auto op = pikoo::text(q.get(), "op");
    auto now_field = pikoo::field(q.get(), "now");
    uint64_t now =
        cJSON_IsNumber(now_field) ? uint64_t(now_field->valuedouble) : 100;
    auto out = pikoo::object();
    requests.clear();
    replies.clear();
    sent.clear();
    if (op == "configure" || op == "validate") {
      pikoo::AgentConfig c;
      std::string error;
      bool ok = pikoo::decode_config(
          pikoo::json(pikoo::field(q.get(), "config")), c, error);
      cJSON_AddBoolToObject(out.get(), "valid", ok);
      cJSON_AddStringToObject(out.get(), "error", error.c_str());
      if (ok && op == "configure") {
        backend.configure(c);
        live.configure(c);
      }
    } else if (op == "start")
      backend.start(pikoo::text(q.get(), "id"),
                    pikoo::json(pikoo::field(q.get(), "history")), now);
    else if (op == "complete") {
      auto token = pikoo::field(q.get(), "token"),
           status = pikoo::field(q.get(), "status");
      backend.complete({uint64_t(token ? token->valuedouble : 0),
                        status ? status->valueint : 0,
                        pikoo::text(q.get(), "body")},
                       now);
    } else if (op == "cancel")
      backend.cancel();
    else if (op == "tick") {
      backend.tick(now);
      live.tick(now);
    } else if (op == "live_start")
      live.start(now, false);
    else if (op == "receive")
      live.receive(pikoo::json(pikoo::field(q.get(), "message")), now);
    else if (op == "snapshot_load")
      cJSON_AddBoolToObject(out.get(), "loaded",
                            store.load(pikoo::text(q.get(), "snapshot")));
    else if (op == "http_begin")
      http = pikoo::HttpResponse{};
    else if (op == "http_feed") {
      auto bytes = pikoo::text(q.get(), "data");
      bool ok = http.feed(bytes.data(), bytes.size());
      if (cJSON_IsTrue(pikoo::field(q.get(), "eof")))
        ok = http.eof() && ok;
      cJSON_AddBoolToObject(out.get(), "ok", ok);
      cJSON_AddBoolToObject(out.get(), "done", http.done());
      cJSON_AddNumberToObject(out.get(), "status", http.status());
      cJSON_AddStringToObject(out.get(), "body", http.body().c_str());
    }
    auto req = cJSON_AddArrayToObject(out.get(), "requests");
    for (const auto &r : requests) {
      auto o = pikoo::object();
      cJSON_AddNumberToObject(o.get(), "token", double(r.token));
      cJSON_AddNumberToObject(o.get(), "deadline", double(r.deadline));
      cJSON_AddStringToObject(o.get(), "url", r.url.c_str());
      cJSON_AddStringToObject(o.get(), "authorization",
                              r.authorization.c_str());
      cJSON_AddStringToObject(o.get(), "body", r.body.c_str());
      cJSON_AddItemToArray(req, o.release());
    }
    auto a = cJSON_AddArrayToObject(out.get(), "replies");
    for (const auto &r : replies)
      cJSON_AddItemToArray(a, cJSON_CreateString(r.c_str()));
    auto ws = cJSON_AddArrayToObject(out.get(), "send");
    for (const auto &r : sent)
      cJSON_AddItemToArray(ws, cJSON_CreateString(r.c_str()));
    cJSON_AddBoolToObject(out.get(), "busy", backend.busy());
    cJSON_AddStringToObject(out.get(), "snapshot", store.snapshot().c_str());
    std::cout << pikoo::json(out.get()) << std::endl;
  }
}
