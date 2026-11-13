// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "pikoo_agent.hpp"
#include "pikoo_backend.hpp"

#include <algorithm>
#include <cstring>
#include <cctype>
#include <ctime>
#include <utility>

namespace pikoo {
namespace {
constexpr unsigned MaxEntries = 32;
constexpr unsigned MaxCalls = 32;
constexpr unsigned MaxHistory = 12;
constexpr size_t MaxText = 512;
constexpr char Persona[] =
    "You are a friendly household voice companion. Only respond to speech "
    "clearly addressed to you or continuing the conversation. "
    "Ignore unrelated household conversations, TV and noise. Stop when "
    "interrupted. Delegate substantive questions and tasks to the client. "
    "Always delegate EVERY read or change of shopping lists, todos and "
    "persistent memory, including requests to remember a preference or fact. "
    "You cannot save, add, change, delete or verify device data yourself. "
    "Before the client returns a successful result, only acknowledge that you "
    "will try; never say the action is done or remembered. A spoken promise "
    "is not a tool result. If delegation fails, explain the failure. "
    "For Chinese requests such as 记住、记一下、加入清单、删除或读出清单, "
    "delegate first and report only the verified result. ";

void set_text(cJSON *o, const char *key, const std::string &value) {
  cJSON_AddStringToObject(o, key, value.c_str());
}

Json event(const char *type) {
  auto o = object();
  set_text(o.get(), "type", type);
  return o;
}

Json copy(const cJSON *value) {
  return Json(cJSON_Duplicate(value, true), cJSON_Delete);
}
cJSON *get(cJSON *value, const char *key) {
  return cJSON_GetObjectItemCaseSensitive(value, key);
}

std::string error(const char *code) {
  auto o = object();
  set_text(o.get(), "error", code);
  return json(o.get());
}

bool string_array(const cJSON *array, unsigned limit) {
  if (!cJSON_IsArray(array) || unsigned(cJSON_GetArraySize(array)) > limit)
    return false;
  for (const cJSON *item = array->child; item; item = item->next)
    if (!cJSON_IsString(item) || !item->valuestring[0] ||
        std::strlen(item->valuestring) > MaxText)
      return false;
  return true;
}

int match(const cJSON *array, const std::string &value) {
  int i = 0;
  for (const cJSON *item = array->child; item; item = item->next, ++i)
    if (value == item->valuestring)
      return i;
  return -1;
}

Json empty_store() {
  auto o = object();
  cJSON_AddNumberToObject(o.get(), "version", 1);
  for (const auto key : {"shopping", "todo", "memory", "calls", "history"})
    cJSON_AddArrayToObject(o.get(), key);
  return o;
}

void add_tool(cJSON *tools, const char *name, const char *description,
              const char *groups) {
  auto o = event("function");
  set_text(o.get(), "name", name);
  set_text(o.get(), "description", description);
  auto schema = parse(
      std::string(
          R"({"type":"object","properties":{"group":{"type":"string","enum":)") +
      groups +
      R"(},"operation":{"type":"string","enum":["list","add","remove","replace","clear"]},"entry":{"type":"string"},"replacement":{"type":"string"},"confirmed":{"type":"boolean"}},"required":["group","operation"],"additionalProperties":false})");
  cJSON_AddItemToObject(o.get(), "parameters", schema.release());
  cJSON_AddItemToArray(tools, o.release());
}
} // namespace

Json tool_schemas(bool search, bool extract) {
  auto tools = Json(cJSON_CreateArray(), cJSON_Delete);
  add_tool(tools.get(), "family_list",
           "Read or modify device shopping and todo lists",
           R"(["shopping","todo"])");
  add_tool(tools.get(), "family_memory",
           "Read memory or change it only at the user's explicit request",
           R"(["memory"])");
  auto add = [&](const char *name, const char *description, const char *key) {
    auto t = event("function");
    set_text(t.get(), "name", name);
    set_text(t.get(), "description", description);
    auto schema = object();
    set_text(schema.get(), "type", "object");
    auto properties = cJSON_AddObjectToObject(schema.get(), "properties");
    set_text(cJSON_AddObjectToObject(properties, key), "type", "string");
    auto required = cJSON_AddArrayToObject(schema.get(), "required");
    cJSON_AddItemToArray(required, cJSON_CreateString(key));
    cJSON_AddBoolToObject(schema.get(), "additionalProperties", false);
    cJSON_AddItemToObject(t.get(), "parameters", schema.release());
    cJSON_AddItemToArray(tools.get(), t.release());
  };
  if (search)
    add("web_search", "Search current public information; return source links",
        "query");
  if (extract)
    add("read_webpage",
        "Extract public HTTPS webpage content through the configured search "
        "provider",
        "url");
  return tools;
}

Json object() { return Json(cJSON_CreateObject(), cJSON_Delete); }
Json parse(const std::string &value) {
  if (value.find('\0') != std::string::npos)
    return Json(nullptr, cJSON_Delete);
  return Json(
      cJSON_ParseWithLengthOpts(value.c_str(), value.size() + 1, nullptr, true),
      cJSON_Delete);
}
std::string json(const cJSON *value) {
  std::unique_ptr<char, decltype(&cJSON_free)> result(
      cJSON_PrintUnformatted(value), cJSON_free);
  return result ? result.get() : "";
}
const cJSON *field(const cJSON *o, const char *key) {
  return cJSON_GetObjectItemCaseSensitive(o, key);
}
std::string text(const cJSON *o, const char *key) {
  auto value = field(o, key);
  return cJSON_IsString(value) ? value->valuestring : "";
}

FamilyStore::FamilyStore(Commit commit)
    : data_(empty_store()), commit_(std::move(commit)) {}

bool FamilyStore::load(const std::string &value) {
  if (value.size() > Capacity)
    return false;
  auto o = parse(value);
  auto version = field(o.get(), "version");
  if (!cJSON_IsNumber(version) || version->valuedouble != 1)
    return false;
  for (const auto key : {"shopping", "todo", "memory"})
    if (!string_array(field(o.get(), key), MaxEntries))
      return false;
  auto calls = field(o.get(), "calls");
  auto history = field(o.get(), "history");
  if (!cJSON_IsArray(calls) || cJSON_GetArraySize(calls) > int(MaxCalls) ||
      !cJSON_IsArray(history) || cJSON_GetArraySize(history) > int(MaxHistory))
    return false;
  for (auto item = calls->child; item; item = item->next) {
    const auto id = text(item, "id");
    if (id.empty() || id.size() > 128)
      return false;
  }
  for (auto item = history->child; item; item = item->next) {
    const auto role = text(item, "role");
    if ((role != "user" && role != "assistant") ||
        text(item, "text").size() > MaxText)
      return false;
  }
  data_ = std::move(o);
  history_dirty_ = false;
  return true;
}

std::string FamilyStore::snapshot() const { return json(data_.get()); }

bool FamilyStore::save(Json next) {
  const auto value = json(next.get());
  if (value.empty() || value.size() > Capacity || !commit_(value))
    return false;
  data_ = std::move(next);
  history_dirty_ = false;
  return true;
}

std::string FamilyStore::call(const std::string &id, const std::string &name,
                              const std::string &arguments) {
  if (id.empty() || id.size() > 128 || arguments.size() > 2048)
    return error("invalid_call");
  const auto o = parse(arguments);
  const auto group = text(o.get(), "group");
  if ((name != "family_list" || (group != "shopping" && group != "todo")) &&
      (name != "family_memory" || group != "memory"))
    return error("unknown_tool");

  const auto operation = text(o.get(), "operation");
  auto result = object();
  if (operation == "list") {
    cJSON_AddItemToObject(result.get(), "entries",
                          copy(field(data_.get(), group.c_str())).release());
    return json(result.get());
  }
  for (auto item = field(data_.get(), "calls")->child; item; item = item->next)
    if (text(item, "id") == id) {
      cJSON_AddBoolToObject(result.get(), "ok", true);
      cJSON_AddBoolToObject(result.get(), "already_applied", true);
      return json(result.get());
    }

  const auto value = text(o.get(), "entry");
  const auto replacement = text(o.get(), "replacement");
  auto next = copy(data_.get());
  auto entries = get(next.get(), group.c_str());
  if (operation == "clear") {
    if (!cJSON_IsTrue(field(o.get(), "confirmed")))
      return error("confirmation_required");
    cJSON_ReplaceItemInObjectCaseSensitive(next.get(), group.c_str(),
                                           cJSON_CreateArray());
  } else {
    if (value.empty() || value.size() > MaxText)
      return error("invalid_entry");
    const auto position = match(entries, value);
    if (operation == "add") {
      if (position < 0) {
        if (cJSON_GetArraySize(entries) >= int(MaxEntries))
          return error("list_full");
        cJSON_AddItemToArray(entries, cJSON_CreateString(value.c_str()));
      }
    } else if (operation == "remove" || operation == "replace") {
      if (position < 0)
        return error("exact_entry_required");
      if (operation == "remove") {
        cJSON_DeleteItemFromArray(entries, position);
      } else {
        if (replacement.empty() || replacement.size() > MaxText)
          return error("invalid_replacement");
        if (replacement != value && match(entries, replacement) >= 0)
          return error("replacement_exists");
        cJSON_ReplaceItemInArray(entries, position,
                                 cJSON_CreateString(replacement.c_str()));
      }
    } else
      return error("unknown_operation");
  }
  // A correction must not be silently undone by replaying older context.
  if (operation != "add")
    cJSON_ReplaceItemInObjectCaseSensitive(next.get(), "history",
                                           cJSON_CreateArray());
  auto calls = get(next.get(), "calls");
  auto call = object();
  set_text(call.get(), "id", id);
  cJSON_AddItemToArray(calls, call.release());
  if (cJSON_GetArraySize(calls) > int(MaxCalls))
    cJSON_DeleteItemFromArray(calls, 0);
  if (!save(std::move(next)))
    return error("storage_failed");
  cJSON_AddBoolToObject(result.get(), "ok", true);
  return json(result.get());
}

bool FamilyStore::remember_turn(const std::string &role,
                                const std::string &content, bool append) {
  if ((role != "user" && role != "assistant") || content.empty() ||
      content.size() > MaxText)
    return false;
  auto next = copy(data_.get());
  auto items = get(next.get(), "history");
  auto last = cJSON_GetArrayItem(items, cJSON_GetArraySize(items) - 1);
  if (append && text(last, "role") == role &&
      text(last, "text").size() + content.size() <= MaxText) {
    const auto joined = text(last, "text") + content;
    cJSON_ReplaceItemInObjectCaseSensitive(last, "text",
                                           cJSON_CreateString(joined.c_str()));
    if (json(next.get()).size() > Capacity)
      return false;
    data_ = std::move(next);
    history_dirty_ = true;
    return true;
  }
  auto turn = object();
  set_text(turn.get(), "role", role);
  set_text(turn.get(), "text", content);
  cJSON_AddItemToArray(items, turn.release());
  if (cJSON_GetArraySize(items) > int(MaxHistory))
    cJSON_DeleteItemFromArray(items, 0);
  if (json(next.get()).size() > Capacity)
    return false;
  data_ = std::move(next);
  history_dirty_ = true;
  return true;
}

bool FamilyStore::flush_history() {
  return !history_dirty_ || save(copy(data_.get()));
}

bool FamilyStore::clear_context() {
  auto next = copy(data_.get());
  cJSON_ReplaceItemInObjectCaseSensitive(next.get(), "history",
                                         cJSON_CreateArray());
  return save(std::move(next));
}

Json FamilyStore::history() const {
  auto input = Json(cJSON_CreateArray(), cJSON_Delete);
  for (auto item = field(data_.get(), "history")->child; item;
       item = item->next) {
    auto message = event("message");
    const auto role = text(item, "role");
    set_text(message.get(), "role", role);
    auto content = cJSON_AddArrayToObject(message.get(), "content");
    auto part = event(role == "assistant" ? "output_text" : "input_text");
    set_text(part.get(), "text", text(item, "text"));
    cJSON_AddItemToArray(content, part.release());
    cJSON_AddItemToArray(input.get(), message.release());
  }
  return input;
}

LiveAgent::LiveAgent(FamilyStore &store, Output output)
    : store_(store), output_(std::move(output)) {}

std::string LiveAgent::send(Json message) {
  const auto id = "pikoo-edge-" + std::to_string(++serial_);
  set_text(message.get(), "event_id", id);
  if (!output_.send(json(message.get())))
    output_.failed(0);
  return id;
}

void LiveAgent::start(uint64_t now, bool greet, unsigned rate) {
  reset();
  if (rate != 16000 && rate != 24000) {
    output_.failed(4003);
    return;
  }
  rate_ = rate;
  effective_ = now;
  greeting_ = greet;
  auto message = event("session.start");
  auto session = cJSON_AddObjectToObject(message.get(), "session");
  set_text(session, "model", config_.live.model);
  cJSON_AddBoolToObject(session, "store", false);
  set_text(session, "instructions",
           std::string(Persona) + " Your name is " + config_.name +
               ". Reply in " + config_.language + ". " + config_.instructions);
  cJSON_AddItemToObject(session, "input", store_.history().release());
  auto audio = cJSON_AddObjectToObject(session, "audio");
  auto format = cJSON_AddObjectToObject(audio, "format");
  set_text(format, "type", "audio/pcm");
  cJSON_AddNumberToObject(format, "rate", rate_);
  set_text(cJSON_AddObjectToObject(audio, "output"), "voice", config_.voice);
  auto triggers = parse(
      R"([{"type":"decisions","event_type":"session.input_transcript.delta","decisions":{"questions":[{"type":"choice","name":"interaction","instructions":"Classify the latest speech in its language and conversational context. Choose interrupt for a request to stop, pause, wait or correct the current reply. Choose farewell only when the user explicitly ends the conversation with Pikoo. Choose addressed for speech directed to Pikoo or continuing the conversation. Choose ignore for unrelated conversations, television, noise, quoted stop words or uncertainty.","choices":[{"value":"addressed"},{"value":"interrupt"},{"value":"farewell"},{"value":"ignore"}]}]}}])");
  cJSON_AddItemToObject(session, "triggers", triggers.release());
  auto delegation = cJSON_AddObjectToObject(session, "delegation");
  set_text(delegation, "type", "client");
  send(std::move(message));
}

void LiveAgent::receive(const std::string &message, uint64_t now) {
  if (message.size() > MessageLimit) {
    output_.failed(0);
    return;
  }
  auto o = parse(message);
  if (!o) {
    output_.failed(0);
    return;
  }
  const auto type = text(o.get(), "type");
  if (type.size() < 80 && event_types_.size() < 32 &&
      event_types_.insert(type).second)
    output_.diagnostic(type.c_str());
  if (type == "session.started" && !ready_) {
    auto session = field(o.get(), "session");
    auto format = field(field(session, "audio"), "format");
    auto rate = field(format, "rate");
    if (format && (text(format, "type") != "audio/pcm" ||
                   !cJSON_IsNumber(rate) || rate->valuedouble != rate_)) {
      output_.failed(4003);
      return;
    }
    auto expires = field(session, "expires_at");
    if (cJSON_IsNumber(expires) && expires->valuedouble > 0 &&
        expires->valuedouble < 4102444800.0)
      expires_at_ = uint64_t(expires->valuedouble);
    ready_ = true;
    output_.ready(rate_);
    if (greeting_) {
      auto greeting = event("session.commentary.append");
      cJSON_AddNullToObject(greeting.get(), "delegation_id");
      set_text(greeting.get(), "content",
               "The user just woke you. Briefly greet in " + config_.language +
                   ", then wait quietly.");
      send(std::move(greeting));
    }
  } else if (type == "error") {
    const auto code = text(field(o.get(), "error"), "code");
    if (code.find("rate_limit") != std::string::npos)
      output_.failed(429);
    else if (code.find("auth") != std::string::npos ||
             code == "responses_validation_failed" ||
             code == "insufficient_quota" || code == "model_not_found")
      output_.failed(4003);
    else
      output_.failed(0);
  } else if (type == "session.closed") {
    output_.failed(0);
  } else if (ready_ && type == "session.output_audio.delta") {
    auto audio = text(o.get(), "delta");
    if (!audio.empty() && interrupt_event_.empty()) {
      audio_at_ = now;
      output_.audio(audio);
    }
  } else if (ready_ && type == "session.instructions.appended" &&
             !interrupt_event_.empty() &&
             text(o.get(), "client_event_id") == interrupt_event_) {
    interrupt_event_.clear();
    const auto end = field(o.get(), "end_ms");
    if (cJSON_IsNumber(end) && end->valuedouble >= 0 &&
        end->valuedouble < 4102444800000.0) {
      interrupt_context_end_ = uint64_t(end->valuedouble);
      awaiting_new_speech_ = true;
    }
    output_.interrupt_ack();
  } else if (ready_ && type == "session.input_transcript.delta") {
    const auto id = text(o.get(), "event_id"),
               fragment = text(o.get(), "delta");
    if (!id.empty() && id.size() <= 256 && !fragment.empty() &&
        fragment.size() <= MaxText &&
        std::none_of(inputs_.begin(), inputs_.end(),
                     [&](const Input &i) { return i.id == id; })) {
      if (inputs_.size() >= 32)
        inputs_.erase(inputs_.begin());
      if (!input_at_ || now - input_at_ > 2500)
        input_window_.clear();
      input_at_ = now;
      input_window_ += fragment;
      if (input_window_.size() > 1024)
        input_window_.erase(0, input_window_.size() - 1024);
      bool stop_phrase = false;
      std::string english = input_window_;
      std::transform(english.begin(), english.end(), english.begin(),
                     [](unsigned char c) { return std::tolower(c); });
      for (const auto phrase : {"stop", "pause", "wait", "hold on", "don't continue",
                                 "do not continue", "that's wrong"}) {
        size_t pos = 0;
        while ((pos = english.find(phrase, pos)) != std::string::npos) {
          const auto end = pos + std::strlen(phrase);
          if ((pos == 0 || !std::isalpha(static_cast<unsigned char>(english[pos-1]))) &&
              (end == english.size() || !std::isalpha(static_cast<unsigned char>(english[end]))))
            stop_phrase = true;
          pos = end;
        }
      }
      if (english.find("don't stop") != std::string::npos ||
          english.find("do not stop") != std::string::npos ||
          english.find("don't pause") != std::string::npos ||
          english.find("do not pause") != std::string::npos)
        stop_phrase = false;
      for (const auto phrase :
           {"停一下", "停下", "等一下", "等一等", "等等", "别讲", "别说",
            "别继续", "先别", "不要继续", "不要讲", "不要说", "不对", "说错了",
            "不是这样"})
        stop_phrase =
            stop_phrase || input_window_.find(phrase) != std::string::npos;
      if (input_window_.find("不要停") != std::string::npos ||
          input_window_.find("别停") != std::string::npos)
        stop_phrase = false;
      inputs_.push_back({id, fragment, now, stop_phrase});
    }
  } else if (ready_ && type == "decision.event") {
    classify(o.get(), now);
  } else if (ready_ && type == "session.output_transcript.delta") {
    effective_ = now;
    if (interrupt_event_.empty()) {
      const auto start = field(o.get(), "start_ms");
      if (awaiting_new_speech_ && cJSON_IsNumber(start)) {
        if (start->valuedouble < interrupt_context_end_)
          return;
        awaiting_new_speech_ = false;
        output_.interrupt_resume();
        output_.diagnostic("edge.interrupt.resumed");
      }
      record_reply(o.get(), now);
    }
  } else if (ready_ && type == "session.delegation.created") {
    const auto d = field(o.get(), "delegation");
    const auto id = text(d, "id");
    if (text(d, "target") == "client" && !id.empty() && id.size() <= 128 &&
        seen_delegations_.find(id) == seen_delegations_.end()) {
      if (delegation_order_.size() == 32) {
        seen_delegations_.erase(delegation_order_.front());
        delegation_order_.erase(delegation_order_.begin());
      }
      seen_delegations_.insert(id);
      delegation_order_.push_back(id);
      output_.cancel();
      delegation_ = id;
      delegation_at_ = now;
      dispatch(now);
    }
  }
}

void LiveAgent::dispatch(uint64_t now) {
  if (farewell_at_) {
    delegation_.clear();
    return;
  }
  if (delegation_.empty() || !inputs_.empty())
    return;
  if (!addressed_at_ || now - addressed_at_ > 5000 ||
      addressed_serial_ <= dispatched_serial_)
    return;
  dispatched_serial_ = addressed_serial_;
  flush_turn();
  auto id = delegation_;
  delegation_.clear();
  output_.delegate(id, json(store_.history().get()), now);
}
void LiveAgent::result(const std::string &id, const std::string &content) {
  if (!ready_ || farewell_at_)
    return;
  auto message = event("session.commentary.append");
  set_text(message.get(), "delegation_id", id);
  set_text(message.get(), "content", content);
  send(std::move(message));
}

void LiveAgent::classify(const cJSON *message, uint64_t now) {
  output_.diagnostic("edge.decision.received");
  const auto source = text(message, "source_event_id");
  auto input = std::find_if(inputs_.begin(), inputs_.end(),
                            [&](const Input &i) { return i.id == source; });
  if (input == inputs_.end() || now - input->at > 5000 ||
      text(message, "source_event_type") != "session.input_transcript.delta")
    return;
  auto e = field(message, "event");
  if (text(e, "type") != "decision.completed")
    return;
  auto answers = field(field(e, "decision"), "answers");
  if (!cJSON_IsArray(answers))
    return;
  for (auto item = answers->child; item; item = item->next) {
    if (text(item, "name") != "interaction")
      continue;
    const auto choice = text(item, "choice");
    if (choice == "farewell") {
      farewell_at_ = now;
      delegation_.clear();
      output_.cancel();
      effective_ = now;
    } else if (choice == "addressed" || choice == "interrupt") {
      farewell_at_ = 0;
      effective_ = now;
      addressed_at_ = now;
      ++addressed_serial_;
      // A partial "不要" is not a stop command: it may become "不要修改".
      // Require both semantic authorization and a complete stop/correction
      // phrase, including phrases split over several transcript deltas.
      const bool interrupt = choice == "interrupt" && input->stop_phrase;
      if (interrupt)
        reply_.clear();
      else
        flush_turn();
      reply_continuation_ = false;
      store_.remember_turn("user", input->fragment, true);
      if (interrupt && (!interrupt_at_ || now - interrupt_at_ >= 2000)) {
        interrupt_at_ = now;
        awaiting_new_speech_ = false;
        input_window_.clear();
        delegation_.clear();
        output_.cancel();
        output_.interrupt();
        output_.diagnostic("edge.interrupt");
        auto instruction = event("session.instructions.append");
        cJSON_AddNullToObject(instruction.get(), "delegation_id");
        set_text(instruction.get(), "content",
                 "The user is interrupting. Stop the previous answer immediately. "
                 "Follow the latest instruction briefly in the configured language. "
                 "If asked only to stop, remain quiet.");
        interrupt_event_ = send(std::move(instruction));
      }
    }
    inputs_.erase(input);
    dispatch(now);
    break;
  }
}

void LiveAgent::record_reply(const cJSON *message, uint64_t now) {
  const auto fragment = text(message, "delta");
  if (fragment.empty())
    return;
  const auto start = field(message, "start_ms"), end = field(message, "end_ms");
  if (cJSON_IsNumber(start) && start->valuedouble >= 0 && reply_end_ &&
      start->valuedouble > reply_end_ + 800) {
    flush_turn();
    reply_continuation_ = false;
  }
  if (cJSON_IsNumber(end) && end->valuedouble >= 0 &&
      end->valuedouble < 4102444800000.0)
    reply_end_ = uint64_t(end->valuedouble);
  size_t offset = 0;
  while (offset < fragment.size()) {
    size_t count = std::min(MaxText - reply_.size(), fragment.size() - offset);
    if (offset + count < fragment.size()) {
      while (count && (static_cast<unsigned char>(fragment[offset + count]) &
                       0xc0) == 0x80)
        --count;
    }
    if (!count) {
      if (reply_.empty())
        break; // Reject an invalid UTF-8 fragment without looping.
      flush_turn();
      continue;
    }
    reply_.append(fragment, offset, count);
    offset += count;
    if (offset < fragment.size())
      flush_turn();
  }
  turn_at_ = now;
}
void LiveAgent::flush_turn() {
  if (!reply_.empty()) {
    store_.remember_turn("assistant", reply_, reply_continuation_);
    reply_continuation_ = true;
  }
  reply_.clear();
  turn_at_ = 0;
}
void LiveAgent::flush_context() {
  flush_turn();
  store_.flush_history();
}
void LiveAgent::tick(uint64_t now) {
  if (!interrupt_event_.empty() && now - interrupt_at_ >= 5000) {
    interrupt_event_.clear();
    ready_ = false;
    output_.failed(0);
  }
  if (turn_at_ && now - turn_at_ >= 900)
    flush_turn();
  inputs_.erase(
      std::remove_if(inputs_.begin(), inputs_.end(),
                     [now](const Input &i) { return now - i.at > 5000; }),
      inputs_.end());
  if (!delegation_.empty() && now - delegation_at_ >= 5000)
    delegation_.clear();
  dispatch(now);
  if (ready_ && expires_at_ &&
      uint64_t(std::time(nullptr)) + 5 >= expires_at_) {
    ready_ = false;
    output_.failed(0);
  }
}
bool LiveAgent::sleep_due(uint64_t now, bool playing) const {
  if (!ready_)
    return false;
  if (farewell_at_)
    return now - farewell_at_ >= 20000 ||
           // Live sends continuous silence too. The board's playing signal
           // tracks voiced samples and actual drain; packet arrival cannot mark
           // speech.
           (!playing && now - farewell_at_ >= 5000);
  return !playing && delegation_.empty() && now - effective_ >= 60000;
}
void LiveAgent::reset() {
  ready_ = false;
  delegation_.clear();
  seen_delegations_.clear();
  delegation_order_.clear();
  addressed_serial_ = dispatched_serial_ = 0;
  addressed_at_ = 0;
  output_.cancel();
  event_types_.clear();
  effective_ = farewell_at_ = audio_at_ = expires_at_ = turn_at_ = 0;
  reply_.clear();
  interrupt_event_.clear();
  interrupt_at_ = 0;
  inputs_.clear();
  input_window_.clear();
  input_at_ = 0;
  awaiting_new_speech_ = false;
  interrupt_context_end_ = 0;
  reply_end_ = 0;
  reply_continuation_ = false;
}

size_t LiveUpload24k::convert(const int16_t *input, size_t count,
                              int16_t *out) {
  if (!count || count % 2)
    return 0;
  if (!have_previous_) {
    previous_ = input[0];
    have_previous_ = true;
  }
  size_t size = 0;
  for (size_t i = 0; i < count; i += 2) {
    const int first = input[i], second = input[i + 1];
    out[size++] = (2 * previous_ + first) / 3;
    out[size++] = first;
    out[size++] = (first + 2 * second) / 3;
    previous_ = second;
  }
  return size;
}

bool safe_header(const std::string &value) {
  return !value.empty() && value.size() <= 1024 &&
         std::all_of(value.begin(), value.end(),
                     [](unsigned char c) { return c > 32 && c < 127; });
}
int connect_status(const std::string &headers) {
  if (headers.size() < 16 || headers.size() > 8192 ||
      headers.substr(headers.size() - 4) != "\r\n\r\n" ||
      (headers.compare(0, 9, "HTTP/1.1 ") &&
       headers.compare(0, 9, "HTTP/1.0 ")) ||
      (headers[12] != ' ' && headers[12] != '\r'))
    return -1;
  int code = 0;
  for (size_t i = 9; i < 12; ++i) {
    if (headers[i] < '0' || headers[i] > '9')
      return -1;
    code = code * 10 + headers[i] - '0';
  }
  return code;
}
} // namespace pikoo
