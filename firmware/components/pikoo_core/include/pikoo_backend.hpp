// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "pikoo_agent.hpp"
namespace pikoo {
struct HttpRequest {
  uint64_t token = 0, deadline = 0;
  std::string url, authorization, body;
};
struct HttpResult {
  uint64_t token = 0;
  int status = 0;
  std::string body;
};
class ToolRegistry {
public:
  using Executor =
      std::function<void(const std::string &, const std::string &, uint64_t)>;
  bool add(const std::string &definition, Executor executor);
  Json schemas() const;
  bool execute(const std::string &name, const std::string &id,
               const std::string &arguments, uint64_t now) const;

private:
  struct Tool {
    std::string name, definition;
    Executor executor;
  };
  std::vector<Tool> tools_;
};
// Invoked only by the session task. Network workers never touch FamilyStore.
class BackendAgent {
public:
  using Request = std::function<void(HttpRequest)>;
  using Reply = std::function<void(const std::string &, const std::string &)>;
  BackendAgent(FamilyStore &store, Request request, Reply reply);
  void configure(const AgentConfig &config);
  void start(const std::string &id, const std::string &history, uint64_t now);
  void complete(const HttpResult &result, uint64_t now);
  void tick(uint64_t now);
  void cancel();
  bool busy() const { return !id_.empty(); }
  uint64_t token() const { return token_; }
  ToolRegistry &tools() { return tools_; }
  // Extensions deliver results on the session task with the captured token.
  bool complete_tool(uint64_t token, const std::string &id,
                     const std::string &value, uint64_t now);

private:
  struct Call {
    std::string id, name, arguments;
  };
  enum class Waiting { Llm, Search, Extract } waiting_ = Waiting::Llm;
  void llm(uint64_t now);
  void advance(uint64_t now);
  void search(const std::string &name, const std::string &arguments,
              uint64_t now);
  void result(const std::string &value, uint64_t now);
  void finish(const std::string &message);
  FamilyStore &store_;
  Request request_;
  Reply reply_;
  AgentConfig config_;
  ToolRegistry tools_;
  std::string id_;
  Json input_{nullptr, cJSON_Delete};
  std::vector<Call> calls_;
  size_t call_ = 0;
  unsigned rounds_ = 0;
  uint64_t token_ = 0, deadline_ = 0;
};
Json tool_schemas(bool search, bool extract);
} // namespace pikoo
