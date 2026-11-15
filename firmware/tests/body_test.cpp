#include "pikoo_body.hpp"
#include <cassert>
#include <iostream>
using namespace pikoo;
int main() {
  int db = -24, brightness = 100, calls = 0;
  bool save = true, fail = false;
  std::string action;
  Body b(
      [&](int v) {
        ++calls;
        if (!fail)
          db = v;
        return Body::Applied{!fail, save && !fail, db};
      },
      [&](int v) {
        brightness = v;
        return Body::Applied{true, save, v};
      },
      [&](const std::string &v) {
        action = v;
        return true;
      });
  b.initialize(db, brightness);
  auto call = [&](std::string id, std::string tool, std::string args,
                  int at = 100) { return parse(b.call(id, tool, args, at)); };
  auto r = call("1", "body_set_audio", R"({"delta_db":3})");
  assert(db == -21 && calls == 1 && cJSON_IsTrue(field(r.get(), "saved")));
  call("1", "body_set_audio", R"({"delta_db":3})");
  assert(db == -21 && calls == 1);
  assert(text(call("1", "body_set_audio", R"({"delta_db":-3})").get(),
              "error") == "call_id_conflict");
  call("2", "body_set_audio", R"({"percent":50})");
  assert(db == -25);
  call("3", "body_set_audio", R"({"delta_db":50})");
  assert(db == 0);
  call("4", "body_set_audio", R"({"delta_db":3})");
  assert(db == 0);
  assert(!text(call("5", "body_set_audio", R"({"gain_db":-51})").get(), "error")
              .empty());
  assert(
      !text(call("6", "body_set_audio", R"({"percent":20.5})").get(), "error")
           .empty());
  call("7", "body_set_display", R"({"delta_percent":-10})");
  assert(brightness == 90);
  call("8", "body_set_display", R"({"percent":0})");
  assert(brightness == 0);
  save = false;
  r = call("9", "body_set_audio", R"({"gain_db":-10})");
  assert(cJSON_IsTrue(field(r.get(), "applied")) &&
         !cJSON_IsTrue(field(r.get(), "saved")));
  fail = true;
  r = call("10", "body_set_audio", R"({"gain_db":-20})");
  assert(!cJSON_IsTrue(field(r.get(), "applied")) && db == -10);
  call("11", "body_perform", R"({"action":"happy"})");
  eyes::Input i;
  i.state = eyes::State::Listening;
  b.input(i, 101);
  assert(i.state == eyes::State::Happy);
  i.state = eyes::State::Listening;
  b.input(i, 3101);
  assert(i.state == eyes::State::Listening);
  call("12", "body_perform", R"({"action":"curious"})");
  i.state = eyes::State::Muted;
  b.input(i, 101);
  assert(i.state == eyes::State::Muted);
  call("13", "body_perform", R"({"action":"look_left"})");
  i.state = eyes::State::Listening;
  b.input(i, 101);
  assert(i.gaze_x == -1);
  call("14", "body_perform", R"({"action":"look_right"})");
  i.gaze_x = 0;
  b.input(i, 101);
  assert(i.gaze_x == 1);
  call("15", "body_perform", R"({"action":"blink_left"})");
  eyes::Pose p;
  p.state = eyes::State::Listening;
  p.blink = 1;
  b.pose(p, 275);
  assert(p.blink == 0);
  assert(p.command_blink > .99 && p.blink_side == 0);
  b.cancel();
  p.command_blink = 0;
  b.pose(p, 275);
  assert(p.command_blink == 0);
  assert(!text(call("16", "body_perform",
                    R"({"action":"happy","duration_ms":10001})")
                   .get(),
               "error")
              .empty());
  call("17", "body_perform", R"({"action":"mute_microphone"})");
  assert(action == "mute_microphone");
  assert(cJSON_IsFalse(
      field(call("", "body_get_state", "{}").get(), "microphone_enabled")));
  FamilyStore store([](const std::string &) { return true; });
  std::string request;
  BackendAgent agent(
      store, [&](HttpRequest r) { request = r.body; },
      [](const std::string &, const std::string &) {});
  AgentConfig config;
  config.llm.protocol = "openai_responses";
  agent.configure(config);
  for (auto &d : Body::definitions())
    assert(agent.tools().add(d, [](auto &, auto &, auto) {}));
  agent.start("a", "[]", 0);
  assert(request.find("body_set_audio") != std::string::npos);
  config.llm.protocol = "openai_chat_completions";
  agent.configure(config);
  for (auto &d : Body::definitions())
    agent.tools().add(d, [](auto &, auto &, auto) {});
  agent.start("b", "[]", 0);
  assert(request.find("body_set_audio") != std::string::npos);
  fail = false;
  save = true;
  call("mode-a", "body_set_audio", R"({"mode":"delta_db","value":3})");
  assert(db == -7);
  call("mode-b", "body_set_audio", R"({"mode":"gain_db","value":-20})");
  assert(db == -20);
  call("mode-c", "body_set_audio", R"({"mode":"percent","value":50})");
  assert(db == -25);
  call("mode-d", "body_set_display", R"({"mode":"delta_percent","value":10})");
  assert(brightness == 10);
  assert(!text(call("conflict", "body_set_audio",
                    R"({"delta_db":3,"gain_db":0,"percent":0})")
                   .get(),
               "error")
              .empty());
  assert(!text(call("mode-invalid", "body_set_audio",
                    R"({"mode":"gain_db","value":100})")
                   .get(),
               "error")
              .empty());
  call("default-duration", "body_perform",
       R"({"action":"happy","duration_ms":null})");
  // Report each applied step immediately, while allowing a compound request
  // to continue through subsequent model/tool rounds.
  for (const auto protocol : {"openai_responses", "openai_chat_completions"}) {
    std::vector<HttpRequest> requests;
    std::vector<std::string> replies, progress;
    BackendAgent direct(
        store, [&](HttpRequest q) { requests.push_back(q); },
        [&](const std::string &, const std::string &v) {
          replies.push_back(v);
        },
        [&](const std::string &, const std::string &v) {
          progress.push_back(v);
        });
    config.llm.protocol = protocol;
    direct.configure(config);
    for (auto &d : Body::definitions()) {
      auto definition = parse(d);
      auto name = text(definition.get(), "name");
      assert(direct.tools().add(d, [&, name](const std::string &id,
                                             const std::string &args,
                                             uint64_t at) {
        auto token = direct.token();
        assert(direct.complete_tool(token, id, b.call(id, name, args, at), at));
      }));
    }
    auto tool_response = [&](const char *name, const char *args,
                             const std::string &id) {
      auto r = object();
      auto call = cJSON_CreateObject();
      if (config.llm.protocol == "openai_responses") {
        cJSON_AddStringToObject(r.get(), "status", "completed");
        auto output = cJSON_AddArrayToObject(r.get(), "output");
        cJSON_AddStringToObject(call, "type", "function_call");
        cJSON_AddStringToObject(call, "call_id", id.c_str());
        cJSON_AddStringToObject(call, "name", name);
        cJSON_AddStringToObject(call, "arguments", args);
        cJSON_AddItemToArray(output, call);
      } else {
        auto choices = cJSON_AddArrayToObject(r.get(), "choices");
        auto choice = cJSON_CreateObject();
        cJSON_AddStringToObject(choice, "finish_reason", "tool_calls");
        auto message = cJSON_AddObjectToObject(choice, "message");
        cJSON_AddStringToObject(message, "role", "assistant");
        auto calls = cJSON_AddArrayToObject(message, "tool_calls");
        cJSON_AddStringToObject(call, "id", id.c_str());
        cJSON_AddStringToObject(call, "type", "function");
        auto f = cJSON_AddObjectToObject(call, "function");
        cJSON_AddStringToObject(f, "name", name);
        cJSON_AddStringToObject(f, "arguments", args);
        cJSON_AddItemToArray(calls, call);
        cJSON_AddItemToArray(choices, choice);
      }
      return json(r.get());
    };
    direct.start("body-roundtrip", "[]", 0);
    auto previous = db;
    auto id = std::string(protocol);
    direct.complete(
        {requests.back().token, 200,
         tool_response("body_set_audio", R"({"mode":"delta_db","value":3})",
                       id + "-volume")},
        100);
    assert(db == previous + 3 && requests.size() == 2 && replies.empty() &&
           progress.size() == 1);
    direct.complete(
        {requests.back().token, 200,
         tool_response("body_perform", R"({"action":"happy"})", id + "-smile")},
        200);
    assert(requests.size() == 3 && replies.empty() && progress.size() == 2);
    auto final =
        config.llm.protocol == "openai_responses"
            ? R"({"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"done"}]}]})"
            : R"({"choices":[{"finish_reason":"stop","message":{"role":"assistant","content":"done"}}]})";
    direct.complete({requests.back().token, 200, final}, 300);
    assert(!direct.busy() && replies.size() == 1 &&
           replies.back().find("body_set_audio") != std::string::npos &&
           replies.back().find("body_perform") != std::string::npos);
    direct.start("body-followup-failure", "[]", 400);
    direct.complete({requests.back().token, 200,
                     tool_response("body_perform", R"({"action":"curious"})",
                                   id + "-partial")},
                    500);
    direct.complete({requests.back().token, 503, "{}"}, 600);
    assert(!direct.busy() &&
           replies.back().find("Authoritative body receipts") !=
               std::string::npos &&
           replies.back().find("applied") != std::string::npos);
  }
  // A step accepted before the deadline may commit just after it. Keep its
  // proof and progress, but never start another step after expiration.
  {
    std::vector<HttpRequest> requests;
    std::vector<std::string> replies, progress;
    BackendAgent deadline(
        store, [&](HttpRequest r) { requests.push_back(r); },
        [&](const std::string &, const std::string &r) {
          replies.push_back(r);
        },
        [&](const std::string &, const std::string &r) {
          progress.push_back(r);
        });
    config.llm.protocol = "openai_responses";
    deadline.configure(config);
    for (const auto &definition : Body::definitions()) {
      auto schema = parse(definition);
      auto name = text(schema.get(), "name");
      deadline.tools().add(definition, [&, name](const std::string &id,
                                                 const std::string &args,
                                                 uint64_t at) {
        auto token = deadline.token();
        auto result = b.call(id, name, args, at);
        assert(deadline.complete_tool(token, id, result, 30001));
      });
    }
    deadline.start("expiry", "[]", 0);
    auto before = calls;
    deadline.complete(
        {requests.back().token, 200,
         R"({"status":"completed","output":[{"type":"function_call","name":"body_set_audio","call_id":"expiry-audio","arguments":"{\"mode\":\"delta_db\",\"value\":3}"},{"type":"function_call","name":"body_perform","call_id":"must-not-run","arguments":"{\"action\":\"happy\"}"}]})"},
        29999);
    assert(calls == before + 1 && progress.size() == 1 && replies.size() == 1 &&
           !deadline.busy());
    assert(replies.back().find("expiry") != std::string::npos ||
           replies.back().find("deadline") != std::string::npos);
    assert(replies.back().find("body_set_audio") != std::string::npos &&
           replies.back().find("body_perform") == std::string::npos);
  }
  // Live can speak a promise without creating a client delegation. Route an
  // addressed body candidate once, while preserving the semantic tool boundary.
  FamilyStore routed_store([](const std::string &) { return true; });
  std::vector<std::string> wire;
  unsigned delegations = 0;
  std::string delegated_id;
  LiveAgent::Output out;
  out.send = [&](const std::string &v) {
    wire.push_back(v);
    return true;
  };
  out.ready = [](unsigned) {};
  out.audio = [](const std::string &) {};
  out.failed = [](int) { assert(false); };
  out.delegate = [&](const std::string &id, const std::string &history,
                     uint64_t) {
    ++delegations;
    delegated_id = id;
    assert(history.find("volume") != std::string::npos);
  };
  LiveAgent live(routed_store, out);
  live.configure(config);
  live.start(100, false);
  live.receive(R"({"type":"session.started"})", 101);
  auto utterance =
      R"({"type":"session.input_transcript.delta","event_id":"body-request","delta":"turn your volume up"})";
  auto addressed =
      R"({"type":"decision.event","source_event_id":"body-request","source_event_type":"session.input_transcript.delta","event":{"type":"decision.completed","decision":{"answers":[{"name":"interaction","choice":"addressed"}]}}})";
  live.receive(utterance, 200);
  live.receive(addressed, 300);
  live.tick(2801);
  assert(delegations == 1);
  live.tick(2802);
  assert(delegations == 1);
  live.receive(
      R"({"type":"session.input_transcript.delta","event_id":"body-tail","delta":" a little"})",
      2850);
  live.receive(
      R"({"type":"decision.event","source_event_id":"body-tail","source_event_type":"session.input_transcript.delta","event":{"type":"decision.completed","decision":{"answers":[{"name":"interaction","choice":"addressed"}]}}})",
      2900);
  live.receive(
      R"({"type":"session.delegation.created","delegation":{"id":"late-provider","target":"client"}})",
      3000);
  assert(delegations == 1);
  live.body_progress(R"({"applied":true,"saved":true,"gain_db":-9})");
  assert(wire.back().find("Verified completed body step") != std::string::npos);
  live.result(delegated_id, "applied and saved");
  assert(wire.back().find("late-provider") != std::string::npos);
  live.reset();
  live.start(2000, false);
  live.receive(R"({"type":"session.started"})", 2001);
  live.receive(utterance, 2100);
  live.receive(
      R"({"type":"decision.event","source_event_id":"body-request","source_event_type":"session.input_transcript.delta","event":{"type":"decision.completed","decision":{"answers":[{"name":"interaction","choice":"ignore"}]}}})",
      2200);
  live.tick(3300);
  assert(delegations == 1);
  std::cout << "Body control boundary, receipts, expiry, priority, failures "
               "and both protocol schemas passed\n";
}
