#include "agent_http.hpp"
#include "agent_storage.hpp"
#include "agent_tunnel.hpp"
#include "board.hpp"
#include "board_audio.hpp"
#include "cJSON.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_afe_sr_models.h"
#include "esp_app_desc.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_private/periph_ctrl.h"
#include "esp_random.h"
#include "esp_sntp.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_transport_ssl.h"
#include "esp_transport_ws.h"
#include "esp_websocket_client.h"
#include "esp_wifi.h"
#include "eye_state.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "hal/usb_serial_jtag_ll.h"
#include "lwip/sockets.h"
#include "lwip/tcp.h"
#include "mbedtls/base64.h"
#include "mbedtls/platform_util.h"
#include "nvs_flash.h"
#include "pikoo_backend.hpp"
#include "pikoo_button.hpp"
#include "pikoo_core.hpp"
#include "pikoo_interaction.hpp"
#include "pikoo_volume.hpp"
#include "wake_model.hpp"
#include "websocket_tx.hpp"
#ifdef PIKOO_WAKE_VETO
#include "wake_verifier.hpp"
#endif
#include "pikoo_continuous.hpp"
#include <atomic>
#include <cstring>
#include <ctime>
#include <deque>
#include <mutex>
#include <set>
#include <string>
#include <vector>

namespace {
using State = pikoo::Session::State;
pikoo::Playback playback;
pikoo::Session session;
pikoo::Interaction interaction;
pikoo::ContinuousStream live_stream;
bool agent_ready = false;
uint64_t local_audio_at = 0;
bool local_interrupt_gate = false;
bool local_interrupt_ack = false;
size_t local_interrupt_quiet = 0;
pikoo::AgentConfig agent_config;
pikoo::FamilyStore family(pikoo::write_family_snapshot);
std::atomic<bool> continuous_audio{false};
std::atomic<bool> voice_connected{false};
std::mutex play_mutex, in_mutex, out_mutex, tx_mutex, tx_io_mutex;
std::deque<std::string> incoming, outgoing;
struct ControlMessage {
  uint32_t connection;
  std::string json;
};
std::deque<ControlMessage> control_queue;
std::atomic<bool> tx_enabled{false};
std::atomic<uint32_t> connection_epoch{0};
std::atomic<bool> tx_hold_requested{false};
std::atomic<uint32_t> session_steps{0}, tx_holds{0};
std::atomic<bool> wifi_ready{false}, uploading{false}, awake{false},
    muted{false}, wake_request{false}, stop_request{false},
    cancel_request{false}, net_open{false}, net_down{false}, overflow{false},
    tone_request{false}, tone_complete{false}, diagnostic_tone{false},
    display_ready{false}, config_ready{false}, finish_request{false};
#ifdef PIKOO_WAKE_VETO
std::atomic<bool> verified_wake_request{false};
std::atomic<uint32_t> verified_wake_epoch{0};
#endif
std::atomic<int> close_code{0}, overflow_reason{0};
std::atomic<uint32_t> send_max_us{0}, send_last_us{0};
std::atomic<uint32_t> transport_stop_max_us{0};
std::atomic<uint32_t> resample_max_us{0}, receive_max_us{0};
std::atomic<uint32_t> playback_gaps{0}, playback_gap_max_us{0};
void fail_queue(int reason) {
  overflow_reason = reason;
  overflow = true;
}
std::atomic<uint64_t> speech_at{0};
std::atomic<uint64_t> display_pause_until{0};
std::atomic<uint32_t> stream_epoch{0};
// 40 ms of PCM plus Base64/JSON fits inside one 4096-byte TLS record.
// A lost TCP segment can take 1.5 s to retransmit with this IDF's defaults.
// Bound recovery to 3.2 s; cancellation/epoch changes still discard everything.
constexpr size_t upload_samples = 640;
constexpr unsigned upload_slots = 80;
static_assert(4 * ((upload_samples * 2 + 2) / 3) + 512 < 4096);
struct Upload {
  uint32_t epoch;
  int count;
  int16_t pcm[upload_samples];
};
QueueHandle_t upload_queue;
// Standby has no speaker playback. Preserve the microphone waveform for the
// model's own microfrontend instead of passing it through conversational AEC.
struct LocalWakeAudio {
  uint32_t epoch, sequence;
  uint16_t count;
  int16_t pcm[512];
};
QueueHandle_t wake_queue;
std::atomic<uint32_t> wake_dropped{0};
// Explicit USB evaluation only. Reboot/default and automatic expiry restore
// ordinary behavior; enabling this never opens a cloud voice session.
std::atomic<uint64_t> wake_test_until_ms{0};
esp_websocket_client_handle_t ws = nullptr;
esp_transport_handle_t tls_transport = nullptr, websocket_transport = nullptr;
std::string ssid, password, device_id, ws_uri, headers, fragment;
uint64_t next_retry = 0, connecting_at = 0;
unsigned retries = 0;
std::atomic<uint32_t> serial{0};
bool active = false;
std::atomic<State> visual_state{State::Idle};
std::atomic<uint32_t> upload_count{0}, reconnect_count{0};
std::atomic<uint32_t> received_audio_count{0};
std::atomic<uint32_t> captured_samples{0}, processed_samples{0},
    uploaded_samples{0};
std::atomic<float> processed_level{0};
uint32_t boot_id;
TaskHandle_t capture_handle = nullptr, process_handle = nullptr,
             playback_handle = nullptr, sender_handle = nullptr,
             backend_handle = nullptr;
const esp_afe_sr_iface_t *afe;
esp_afe_sr_data_t *afe_data;
uint64_t now() { return esp_timer_get_time() / 1000; }
void cancel_backend();
void enqueue_backend(const std::string &, const std::string &, uint64_t);
bool enqueue_control(std::string json);
void play_local_audio(const std::string &b64);
void clear_audio(bool notify);
pikoo::LiveAgent
    agent(family, {enqueue_control,
                   [](unsigned rate) {
                     {
                       std::lock_guard<std::mutex> lock(play_mutex);
                       if (!playback.set_sample_rate(rate)) {
                         fail_queue(4);
                         return;
                       }
                     }
                     live_stream.ready("local", connection_epoch.load());
                     continuous_audio = true;
                     session.voice_ready(now());
                     voice_connected = true;
                     interaction.greeting_sent();
                     uploading = true;
                     session.state = State::Listening;
                   },
                   play_local_audio,
                   [](int code) {
                     ESP_LOGW("pikoo", "edge transport failed code=%d", code);
                     close_code = code;
                     net_down = true;
                   },
                   [](const char *type) {
#ifdef PIKOO_AGENT_TRACE
                     ESP_LOGI("pikoo", "edge event=%s", type);
#else
                     if (!strcmp(type, "edge.tool.ok") ||
                         !strcmp(type, "edge.tool.error") ||
                         !strncmp(type, "edge.interrupt", 14))
                       ESP_LOGI("pikoo", "edge event=%s", type);
#endif
                   },
                   [] {
                     local_interrupt_gate = true;
                     local_interrupt_ack = false;
                     local_interrupt_quiet = 0;
                     local_audio_at = 0;
                     clear_audio(false);
                     // This is one continuous stream: reuse its ID after
                     // discarding the old generation. cancel() alone
                     // permanently rejects that ID.
                     std::lock_guard<std::mutex> lock(play_mutex);
                     playback.reset();
                   },
                   [] { local_interrupt_ack = true; },
                   [] {
                     // The first post-instruction speech on the session
                     // timeline can resume without waiting for a pause and
                     // swallowing its opening words.
                     local_interrupt_gate = false;
                     local_interrupt_quiet = 0;
                   },
                   enqueue_backend, cancel_backend});
std::mutex backend_mutex;
std::deque<pikoo::HttpRequest> backend_requests;
std::deque<pikoo::HttpResult> backend_results;
std::atomic<uint64_t> backend_token{0};
std::atomic<uint64_t> backend_scope{0};
std::atomic<size_t> playback_peak_samples{0};
std::atomic<size_t> upload_peak_frames{0};
pikoo::BackendAgent backend(
    family,
    [](pikoo::HttpRequest request) {
      backend_token = request.token;
      backend_scope = request.scope;
      std::lock_guard<std::mutex> lock(backend_mutex);
      backend_requests.clear();
      backend_requests.push_back(std::move(request));
    },
    [](const std::string &id, const std::string &result) {
      agent.result(id, result);
    });
void cancel_backend() {
  backend.cancel();
  backend_token = backend.token();
  backend_scope = backend.scope();
  std::lock_guard<std::mutex> lock(backend_mutex);
  backend_requests.clear();
  backend_results.clear();
}
void enqueue_backend(const std::string &id, const std::string &history,
                     uint64_t at) {
  backend.start(id, history, at);
}
void backend_task(void *) {
  while (true) {
    pikoo::HttpRequest request;
    bool have = false;
    {
      std::lock_guard<std::mutex> lock(backend_mutex);
      if (!backend_requests.empty()) {
        request = std::move(backend_requests.front());
        backend_requests.pop_front();
        have = true;
      }
    }
    if (have) {
      const auto started = now();
      auto result =
          pikoo::service_request(request, agent_config.network, backend_token,
                                 backend_scope);
      ESP_LOGI("pikoo",
               "backend http_status=%d duration_ms=%llu internal_min=%u "
               "largest=%u cancelled=%d",
               result.status, (unsigned long long)(now() - started),
               unsigned(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL)),
               unsigned(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)),
               int(backend_token != request.token));
      mbedtls_platform_zeroize(request.authorization.data(),
                               request.authorization.size());
      std::lock_guard<std::mutex> lock(backend_mutex);
      if (backend_results.size() < 2)
        backend_results.push_back(std::move(result));
    } else {
      pikoo::service_request_idle(backend_scope);
      vTaskDelay(pdMS_TO_TICKS(10));
    }
  }
}
bool local_wake_test() { return now() < wake_test_until_ms.load(); }
std::string field(cJSON *o, const char *key) {
  auto x = cJSON_GetObjectItem(o, key);
  return cJSON_IsString(x) ? x->valuestring : "";
}
std::string encode(const int16_t *p, size_t bytes) {
  std::string result(4 * ((bytes + 2) / 3) + 1, '\0');
  size_t n = 0;
  mbedtls_base64_encode(reinterpret_cast<unsigned char *>(result.data()),
                        result.size(), &n,
                        reinterpret_cast<const unsigned char *>(p), bytes);
  result.resize(n);
  return result;
}
std::string stringify(cJSON *o) {
  char *p = cJSON_PrintUnformatted(o);
  std::string s = p ? p : "";
  cJSON_free(p);
  cJSON_Delete(o);
  return s;
}
cJSON *event(const char *type) {
  auto o = cJSON_CreateObject();
  cJSON_AddStringToObject(o, "type", type);
  char id[80];
  snprintf(id, sizeof(id), "%s-%08lx-%lu", device_id.c_str(),
           static_cast<unsigned long>(boot_id),
           static_cast<unsigned long>(++serial));
  cJSON_AddStringToObject(o, "event_id", id);
  return o;
}
bool enqueue_control(std::string s) {
  if (!tx_enabled)
    return false;
  std::lock_guard<std::mutex> lock(tx_mutex);
  if (control_queue.size() >= 64) {
    fail_queue(9);
    return false;
  }
  control_queue.push_back({connection_epoch.load(), std::move(s)});
  return true; // Accepted by the bounded TX queue, not a delivery receipt.
}
bool send_wire(const std::string &s, uint32_t connection,
               uint32_t audio_epoch = UINT32_MAX, int samples = 0) {
  std::lock_guard<std::mutex> lock(tx_io_mutex);
  if (!tx_enabled || connection != connection_epoch)
    return false;
  if (samples && (!uploading || audio_epoch != stream_epoch))
    return false;
  if (ws && esp_websocket_client_is_connected(ws)) {
    auto started = esp_timer_get_time();
    int sent = esp_websocket_client_send_text(ws, s.data(), s.size(),
                                              pdMS_TO_TICKS(2500));
    auto elapsed = static_cast<uint32_t>(esp_timer_get_time() - started);
    send_last_us = elapsed;
    send_max_us = std::max(send_max_us.load(), elapsed);
    if (sent == int(s.size())) {
      if (samples) {
        ++upload_count;
        uploaded_samples += samples;
      }
      return true;
    }
    net_down = true;
  }
  return false;
}
void receipt(const char *type, const std::string &id) {
  std::lock_guard<std::mutex> lock(out_mutex);
  auto o = cJSON_CreateObject();
  cJSON_AddStringToObject(o, "type", type);
  cJSON_AddStringToObject(o, "responseId", id.c_str());
  if (outgoing.size() < 64)
    outgoing.push_back(stringify(o));
  else
    fail_queue(1);
}
void clear_audio(bool notify) {
  std::lock_guard<std::mutex> lock(play_mutex);
  board::silence();
  tone_request = false;
  tone_complete = false;
  for (auto &id : playback.cancel())
    if (notify)
      receipt("playback.cancelled", id);
}
void gate_off() {
#ifdef PIKOO_WAKE_VETO
  verified_wake_request = false;
  wake_verifier_invalidate();
#endif
  wake_cancel_diagnostics();
  uploading = false;
  ++stream_epoch;
  xQueueReset(upload_queue);
}
void end_socket() {
  const auto stopping_at = esp_timer_get_time();
  tx_enabled = false;
  ++connection_epoch;
  {
    std::lock_guard<std::mutex> lock(tx_mutex);
    control_queue.clear();
  }
  voice_connected = false;
  gate_off();
  active = false;
  awake = false;
  continuous_audio = false;
  live_stream.clear(live_stream.epoch + 1);
  clear_audio(false);
  if (ws) {
    // close(timeout) sends its CLOSE frame with portMAX_DELAY in the pinned
    // client. Wake blocked socket IO first, then join before freeing anything.
    pikoo::abort_tunnel(tls_transport);
    // Shutdown must precede this lock: the sender may be blocked in TLS IO.
    std::lock_guard<std::mutex> lock(tx_io_mutex);
    esp_websocket_client_stop(ws);
    esp_websocket_client_destroy(ws);
    ws = nullptr;
  }
  pikoo::release_frame_writer();
  if (websocket_transport) {
    esp_transport_destroy(websocket_transport);
    websocket_transport = nullptr;
  }
  if (tls_transport) {
    esp_transport_destroy(tls_transport);
    tls_transport = nullptr;
  }
  {
    mbedtls_platform_zeroize(headers.data(), headers.size());
    headers.clear();
    local_audio_at = 0;
    local_interrupt_gate = local_interrupt_ack = false;
    local_interrupt_quiet = 0;
    agent.flush_context();
    agent.reset();
  }
  net_open = false;
  net_down = false;
  {
    std::lock_guard<std::mutex> l(in_mutex);
    incoming.clear();
  }
  {
    std::lock_guard<std::mutex> l(play_mutex);
    playback.reset();
  }
  {
    std::lock_guard<std::mutex> l(out_mutex);
    outgoing.clear();
  }
  transport_stop_max_us =
      std::max(transport_stop_max_us.load(),
               uint32_t(esp_timer_get_time() - stopping_at));
}
void socket_event(void *, esp_event_base_t, int32_t id, void *data) {
  auto e = static_cast<esp_websocket_event_data_t *>(data);
  if (id == WEBSOCKET_EVENT_CONNECTED) {
    int fd = esp_transport_get_socket(tls_transport), enabled = 1;
    int result =
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &enabled, sizeof(enabled));
    ESP_LOGI("pikoo", "low latency socket configured=%d", result == 0);
    net_open = true;
    return;
  }
  if (id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_CLOSED) {
    voice_connected = false;
    if (e && e->close_status_code)
      close_code = e->close_status_code;
    net_down = true;
    gate_off();
    board::silence();
    return;
  }
  if (id == WEBSOCKET_EVENT_ERROR) {
    voice_connected = false;
    if (e) {
      int status = e->error_handle.esp_ws_handshake_status_code;
      const int proxy_status = pikoo::tunnel_status(tls_transport);
      if (status == 401 || status == 403 || proxy_status == 403 ||
          proxy_status == 407)
        close_code = 4003;
      else if (status == 429)
        close_code = 429;
    }
    net_down = true;
    return;
  }
  if (id != WEBSOCKET_EVENT_DATA || !e)
    return;
  if (e->op_code == 8 && e->data_len >= 2) {
    close_code = (uint8_t(e->data_ptr[0]) << 8) | uint8_t(e->data_ptr[1]);
    return;
  }
  if (e->op_code != 1 && e->op_code != 0)
    return;
  if (e->op_code == 1 && e->payload_offset == 0)
    fragment.clear();
  if (e->data_len < 0 ||
      fragment.size() + e->data_len > pikoo::LiveAgent::MessageLimit) {
    fail_queue(2);
    return;
  }
  fragment.append(e->data_ptr, e->data_len);
  if (e->fin && e->payload_offset + e->data_len == e->payload_len) {
    std::lock_guard<std::mutex> lock(in_mutex);
    if (incoming.size() < 32)
      incoming.push_back(std::move(fragment));
    else
      fail_queue(3);
    fragment.clear();
  }
}
void begin() {
  if (local_wake_test())
    return;
  if (muted || !wifi_ready || time(nullptr) < 1700000000) {
    session.state = muted ? State::Muted : State::Offline;
    return;
  }
  end_socket();
  if (!agent_ready) {
    session.state = State::AuthError;
    return;
  }
  close_code = 0;
  session.wake(now());
  active = true;
  awake = true;
  connecting_at = now();
  ++reconnect_count;
  ws_uri = agent_config.live.url;
  headers =
      agent_config.live.api_key.empty()
          ? ""
          : "Authorization: " + agent_config.live.authorization() + "\r\n";
  // The public external-transport API exposes the owned TLS socket, allowing
  // TCP_NODELAY. Otherwise split WS header/payload writes can stall on Nagle.
  tls_transport = pikoo::service_transport(agent_config.network);
  if (!tls_transport) {
    net_down = true;
    return;
  }
  esp_transport_set_default_port(tls_transport, 443);
  websocket_transport = esp_transport_ws_init(tls_transport);
  if (!websocket_transport) {
    net_down = true;
    return;
  }
  esp_transport_set_default_port(websocket_transport, 443);
  auto path = pikoo::endpoint(ws_uri, "wss").path;
  esp_transport_ws_config_t transport_config{};
  transport_config.ws_path = path.c_str();
  transport_config.headers = headers.c_str();
  transport_config.propagate_control_frames = true;
  if (esp_transport_ws_set_config(websocket_transport, &transport_config) !=
      ESP_OK) {
    net_down = true;
    return;
  }
  esp_websocket_client_config_t cfg{};
  cfg.uri = ws_uri.c_str();
  cfg.headers = headers.c_str();
  cfg.ext_transport = websocket_transport;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.disable_auto_reconnect = true;
  cfg.buffer_size = 8192;
  cfg.task_stack = 12288;
  cfg.task_core_id_set = true;
  cfg.task_core_id = 1;
  cfg.task_prio = 5;
  cfg.network_timeout_ms = 10000;
  cfg.ping_interval_sec = 20;
  ws = esp_websocket_client_init(&cfg);
  if (!ws) {
    net_down = true;
    return;
  }
  if (!pikoo::bind_frame_writer(websocket_transport, tls_transport)) {
    net_down = true;
    return;
  }
  tx_enabled = true;
  esp_websocket_register_events(ws, WEBSOCKET_EVENT_ANY, socket_event, nullptr);
  esp_websocket_client_start(ws);
}
void play_local_audio(const std::string &b64) {
  if (!session.ready || !active || muted || b64.size() > 60 * 1024)
    return;
  std::vector<int16_t> pcm((b64.size() * 3 / 4 + 4) / 2);
  size_t bytes = 0;
  if (mbedtls_base64_decode(reinterpret_cast<unsigned char *>(pcm.data()),
                            pcm.size() * 2, &bytes,
                            reinterpret_cast<const unsigned char *>(b64.data()),
                            b64.size()) != 0 ||
      bytes % 2) {
    fail_queue(4);
    return;
  }
  const bool voiced =
      std::any_of(pcm.begin(), pcm.begin() + bytes / 2,
                  [](int16_t sample) { return sample > 100 || sample < -100; });
  if (local_interrupt_gate) {
    // Acknowledgment alone does not delimit played audio. Drop the old tail
    // until the continuous stream also has a short quiet interval.
    local_interrupt_quiet = voiced ? 0 : local_interrupt_quiet + bytes / 2;
    if (local_interrupt_ack &&
        local_interrupt_quiet >= agent_config.audio_rate * 120 / 1000)
      local_interrupt_gate = false;
    return;
  }
  if (voiced)
    local_audio_at = now();
  ++received_audio_count;
  std::lock_guard<std::mutex> lock(play_mutex);
  if (!playback.append(live_stream.id, pcm.data(), bytes / 2))
    fail_queue(5);
  playback_peak_samples =
      std::max(playback_peak_samples.load(), playback.queued());
}
void playback_task(void *) {
  pikoo::Resampler converter;
  uint32_t current = UINT32_MAX;
  std::string response;
  int64_t last_block = 0;
  unsigned logged_gaps = 0;
  struct Pending {
    std::string id;
    size_t samples;
    uint32_t epoch;
    uint64_t due;
  };
  std::deque<Pending> pending;
  while (true) {
    if (tone_request.exchange(false)) {
      std::vector<int16_t> tone(1280);
      for (int i = 0; i < 1280; i++)
        tone[i] = 1800 * std::sin(2 * M_PI * 660 * i / 16000);
      auto epoch = board::generation();
      if (board::play(tone.data(), 1280, epoch)) {
        board::drain();
        if (epoch == board::generation())
          tone_complete = true;
      }
    }
    if (diagnostic_tone.exchange(false)) {
      std::vector<int16_t> tone(2880);
      auto epoch = board::generation();
      for (int frequency : {700, 1000}) {
        for (int i = 0; i < 2880; i++)
          tone[i] = 1800 *
                    std::min(1.f, std::min(i / 160.f, (2879 - i) / 160.f)) *
                    std::sin(2 * M_PI * frequency * i / 16000);
        if (!board::play(tone.data(), 2880, epoch))
          break;
        board::drain();
        vTaskDelay(pdMS_TO_TICKS(100));
      }
      board::silence();
      ESP_LOGI("diag",
               "short tone finished; mic_peak=%.5f ref_peak=%.5f "
               "playback_stack_free=%u; human sound/heat check required",
               board::microphone_peak(), board::reference_peak(),
               unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    }
    const bool keep_output_ready = awake.load() && !muted.load();
    if (keep_output_ready)
      board::prepare_playback(board::generation());
    board::playback_idle(keep_output_ready);
    pikoo::Playback::Chunk chunk;
    bool have = false, started = false;
    size_t prefetched = 0;
    {
      std::lock_guard<std::mutex> lock(play_mutex);
      prefetched = playback.queued();
      have = playback.take(chunk, playback.initial_samples(), now(),
                           pikoo::Playback::MaxInitialWaitMs, continuous_audio);
      if (have)
        started = playback.started(chunk);
    }
    if (have) {
      if (current != chunk.epoch || response != chunk.id) {
        converter.reset();
        current = chunk.epoch;
        response = chunk.id;
        last_block = 0;
        logged_gaps = 0;
      }
      const auto generation = board::generation();
      {
        std::lock_guard<std::mutex> lock(play_mutex);
        if (chunk.epoch != playback.epoch())
          continue;
      }
      // Convert only 10 ms at a time. Converting a whole server chunk before
      // feeding I2S creates a silence gap whenever it exceeds the DMA depth.
      bool played = true;
      const size_t block_samples = chunk.sample_rate / 100;
      for (size_t pos = 0; pos < chunk.pcm.size(); pos += block_samples) {
        auto entered = esp_timer_get_time();
        if (last_block && entered - last_block > 45000) {
          auto gap = uint32_t(entered - last_block);
          ++playback_gaps;
          playback_gap_max_us = std::max(playback_gap_max_us.load(), gap);
          if (logged_gaps++ < 5)
            ESP_LOGW("pikoo", "audio supply gap us=%lu", (unsigned long)gap);
        }
        auto conversion_started = esp_timer_get_time();
        const size_t count = std::min(block_samples, chunk.pcm.size() - pos);
        bool written;
        if (chunk.sample_rate == 16000) {
          written = board::play(chunk.pcm.data() + pos, count, generation);
        } else {
          auto output = converter.process(chunk.pcm.data() + pos, count);
          resample_max_us =
              std::max(resample_max_us.load(),
                       uint32_t(esp_timer_get_time() - conversion_started));
          written = board::play(output.data(), output.size(), generation);
        }
        if (!written) {
          played = false;
          break;
        }
        last_block = esp_timer_get_time();
        if (started) {
          ESP_LOGI("pikoo",
                   "audio first block queued samples=%u rate=%u prefill_ms=%u",
                   unsigned(chunk.pcm.size()), chunk.sample_rate,
                   unsigned(prefetched * 1000 / chunk.sample_rate));
          receipt("playback.started", chunk.id);
          started = false;
        }
      }
      if (played) {
        pending.push_back(
            {chunk.id, chunk.pcm.size(), chunk.epoch, now() + 50});
      } else if (generation == board::generation())
        fail_queue(6);
    } else
      vTaskDelay(pdMS_TO_TICKS(5));
    {
      std::lock_guard<std::mutex> lock(play_mutex);
      while (!pending.empty() && pending.front().due <= now()) {
        auto &p = pending.front();
        playback.drained(p.id, p.samples, p.epoch);
        pending.pop_front();
      }
      for (const auto &id : playback.completed())
        receipt("playback.ended", id);
      if (playback.exhausted())
        fail_queue(7);
    }
  }
}
void capture_task(void *) {
  int count = afe->get_feed_chunksize(afe_data);
  std::vector<int16_t> pcm(count * 2);
  LocalWakeAudio local{};
  uint32_t sequence = 0;
  configASSERT(count <= 512);
  while (true) {
    if (board::capture(pcm.data(), count)) {
      captured_samples += count;
      afe->feed(afe_data, pcm.data());
      if (!awake && !muted) {
        local.epoch = stream_epoch.load();
        local.sequence = ++sequence;
        local.count = count;
        for (int i = 0; i < count; ++i)
          local.pcm[i] = pcm[2 * i];
        if (xQueueSend(wake_queue, &local, 0) != pdTRUE) {
          ++wake_dropped;
          xQueueReset(wake_queue);
          xQueueSend(wake_queue, &local, 0);
        }
      }
    } else
      vTaskDelay(pdMS_TO_TICKS(10));
  }
}
void processing_task(void *) {
  bool was_awake = true;
  uint32_t wake_sequence = 0, wake_epoch = UINT32_MAX;
  LocalWakeAudio local{};
  std::vector<int16_t> packet(upload_samples);
  size_t used = 0;
  uint32_t packet_epoch = 0;
  while (true) {
    auto r = afe->fetch_with_delay(afe_data, pdMS_TO_TICKS(100));
    if (!r || r->ret_value != ESP_OK)
      continue;
    size_t samples = r->data_size / 2;
    processed_samples += samples;
    float power = 0;
    for (size_t j = 0; j < samples; j++)
      power += float(r->data[j]) * r->data[j];
    processed_level = samples ? std::sqrt(power / samples) / 32768.f : 0;
    const bool a = awake;
    const auto epoch = stream_epoch.load();
    if (muted) {
      used = 0;
      continue;
    }
    if (!a) {
      if (was_awake) {
        wake_reset();
#ifdef PIKOO_WAKE_VETO
        wake_verifier_reset();
#endif
        wake_sequence = 0;
        xQueueReset(wake_queue);
      }
      pikoo::pump_bounded(
          2, [&] { return xQueueReceive(wake_queue, &local, 0) == pdTRUE; },
          [&] {
            if (local.epoch != epoch)
              return;
            if (wake_epoch != local.epoch ||
                (wake_sequence && local.sequence != wake_sequence + 1)) {
              wake_reset();
#ifdef PIKOO_WAKE_VETO
              wake_verifier_reset();
#endif
            }
            wake_epoch = local.epoch;
            wake_sequence = local.sequence;
#ifdef PIKOO_WAKE_VETO
            if (wake_verifier_feed(local.pcm, local.count, local.epoch)) {
              verified_wake_epoch = local.epoch;
              verified_wake_request = true;
            }
#else
            if (wake_feed(local.pcm, local.count))
              wake_request = true;
#endif
          });
    } else {
      xQueueReset(wake_queue);
    }
    was_awake = a;
    if (uploading) {
      if (r->vad_state == VAD_SPEECH && board::microphone_level() > .001f)
        speech_at = now();
      if (packet_epoch != epoch) {
        used = 0;
        packet_epoch = epoch;
      }
      size_t pos = 0;
      while (pos < samples) {
        size_t n = std::min<size_t>(upload_samples - used, samples - pos);
        memcpy(packet.data() + used, r->data + pos, n * 2);
        used += n;
        pos += n;
        if (used == upload_samples) {
          Upload u{};
          u.epoch = epoch;
          u.count = upload_samples;
          memcpy(u.pcm, packet.data(), upload_samples * sizeof(int16_t));
          used = 0;
          if (!xQueueSend(upload_queue, &u, 0))
            fail_queue(8);
          upload_peak_frames =
              std::max(upload_peak_frames.load(),
                       size_t(uxQueueMessagesWaiting(upload_queue)));
        }
      }
    } else
      used = 0;
  }
}
std::string setting(nvs_handle_t nvs, const char *key) {
  size_t size = 0;
  if (nvs_get_str(nvs, key, nullptr, &size) != ESP_OK || size > 4096)
    return "";
  std::string s(size, '\0');
  if (nvs_get_str(nvs, key, s.data(), &size) != ESP_OK)
    return "";
  s.resize(size - 1);
  return s;
}
void wifi_event(void *, esp_event_base_t base, int32_t id, void *) {
  if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
    wifi_ready = true;
  } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
    wifi_ready = false;
    gate_off();
    net_down = true;
    board::silence();
    esp_wifi_connect();
  }
}
void publish_state() { visual_state = session.state; }
void graphics_task(void *) {
  pikoo::eyes::Animator animator;
  while (true) {
    auto started = now();
    auto state = visual_state.load();
    // USB-only A/B diagnosis; automatically recover animation after two
    // minutes. Does not change audio, model, volume or persistent
    // configuration.
    if (started < display_pause_until.load()) {
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    pikoo::eyes::Input input{};
    input.state = pikoo::eye_state(state);
    if (!voice_connected &&
        (state == State::Listening || state == State::Thinking ||
         state == State::Speaking))
      input.state = pikoo::eyes::State::Offline;
    input.time_ms = started;
    input.level =
        std::min(1.f, (state == State::Speaking ? board::output_level()
                                                : board::microphone_level()) *
                          8);
    const char *label = "";
    if (!config_ready) {
      input.state = pikoo::eyes::State::Boot;
      label = "USB SETUP";
    } else if (local_wake_test())
      label = state == State::Muted ? "TEST MIC OFF" : "WAKE TEST";
    else if (state == State::Muted)
      label = "MIC OFF";
    else if (state == State::Offline)
      label = "OFFLINE";
    else if (state == State::Connecting)
      label = "CONNECTING";
    else if (state == State::AuthError)
      label = "CHECK CONFIG";
    if (display_ready)
      board::display_frame(animator.update(input), label);
    auto elapsed = now() - started;
    vTaskDelay(pdMS_TO_TICKS(elapsed < 50 ? 50 - elapsed : 1));
  }
}
void control_action(pikoo::Button::Action action) {
  if (!config_ready)
    return;
  if (action == pikoo::Button::Double) {
    board::silence();
    gate_off();
    finish_request = true;
    stop_request = true;
  } else if (action == pikoo::Button::Press) {
    auto state = visual_state.load();
    if (state == State::Speaking || state == State::Thinking) {
      board::silence();
      cancel_request = true;
    } else if (state == State::Idle || state == State::Offline)
      wake_request = true;
  } else if (action == pikoo::Button::Hold) {
    muted = !muted;
    gate_off();
    board::silence();
    if (config_ready)
      board::capture_enabled(!muted);
    stop_request = true;
  }
}
void diagnostics() {
#ifdef PIKOO_WAKE_VETO
  ESP_LOGI("wake_veto",
           "candidates=%lu rejected=%lu cancelled=%lu errors=%lu last_us=%lu",
           (unsigned long)wake_verifier_candidates(),
           (unsigned long)wake_verifier_rejected(),
           (unsigned long)wake_verifier_cancelled(),
           (unsigned long)wake_verifier_errors(),
           (unsigned long)wake_verifier_last_us());
#endif
  wifi_ap_record_t ap{};
  int rssi = esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
  ESP_LOGI(
      "diag",
      "board=%s version=%s state=%d wifi=%d muted=%d upload=%d frames=%lu "
      "reconnects=%lu heap=%u min_heap=%u internal=%u internal_min=%u "
      "largest=%u playback_peak_samples=%u upload_peak_frames=%u "
      "backend_stack_free=%u psram=%u fps=%.1f "
      "mic=%.5f ref=%.5f output=%.5f rx_errors=%lu tx_errors=%lu reset=%d "
      "uptime_ms=%llu wake_max_us=%lu wake_calls=%lu capture_stack_free=%u "
      "process_stack_free=%u mic_peak=%.5f ref_peak=%.5f received_audio=%lu "
      "captured_samples=%lu processed_samples=%lu uploaded_samples=%lu "
      "processed_level=%.5f render_us=%lu transfer_us=%lu send_us=%lu "
      "send_max_us=%lu resample_max_us=%lu receive_max_us=%lu volume_db=%d "
      "dac_reg=%d rssi=%d playback_gaps=%lu playback_gap_max_us=%lu "
      "wake_score=%.3f wake_peak=%.3f wake_raw_peak=%.3f wake_hits=%lu "
      "wake_errors=%lu wake_dropped=%lu wake_test=%d veto_candidates=%lu "
      "veto_rejected=%lu veto_cancelled=%lu veto_errors=%lu veto_last_us=%lu "
      "frame_tx=%lu frame_tx_errors=%lu stop_max_us=%lu upload_pending=%u "
      "session_steps=%lu tx_holds=%lu sender_stack_free=%u "
      "wake_model_sha=%s wake_policy_sha=%s",
      board::Name, esp_app_get_description()->version, int(visual_state.load()),
      int(wifi_ready.load()), int(muted.load()), int(uploading.load()),
      (unsigned long)upload_count.load(), (unsigned long)reconnect_count.load(),
      unsigned(esp_get_free_heap_size()),
      unsigned(esp_get_minimum_free_heap_size()),
      unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
      unsigned(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL)),
      unsigned(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)),
      unsigned(playback_peak_samples.load()),
      unsigned(upload_peak_frames.load()),
      unsigned(backend_handle ? uxTaskGetStackHighWaterMark(backend_handle) : 0),
      unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
      board::display_fps(), board::microphone_level(), board::reference_level(),
      board::output_level(), (unsigned long)board::capture_errors(),
      (unsigned long)board::playback_errors(), int(esp_reset_reason()),
      (unsigned long long)now(), (unsigned long)wake_max_inference_us(),
      (unsigned long)wake_inference_count(),
      unsigned(capture_handle ? uxTaskGetStackHighWaterMark(capture_handle)
                              : 0),
      unsigned(process_handle ? uxTaskGetStackHighWaterMark(process_handle)
                              : 0),
      board::microphone_peak(), board::reference_peak(),
      (unsigned long)received_audio_count.load(),
      (unsigned long)captured_samples.load(),
      (unsigned long)processed_samples.load(),
      (unsigned long)uploaded_samples.load(), processed_level.load(),
      (unsigned long)board::display_render_us(),
      (unsigned long)board::display_transfer_us(),
      (unsigned long)send_last_us.load(), (unsigned long)send_max_us.load(),
      (unsigned long)resample_max_us.load(),
      (unsigned long)receive_max_us.load(), board::volume_db(),
      board::volume_register(), rssi, (unsigned long)playback_gaps.load(),
      (unsigned long)playback_gap_max_us.load(), wake_score(),
      wake_peak_score(), wake_raw_peak_score(),
      (unsigned long)wake_detection_count(), (unsigned long)wake_error_count(),
      (unsigned long)wake_dropped.load(), int(local_wake_test()),
#ifdef PIKOO_WAKE_VETO
      (unsigned long)wake_verifier_candidates(),
      (unsigned long)wake_verifier_rejected(),
      (unsigned long)wake_verifier_cancelled(),
      (unsigned long)wake_verifier_errors(),
      (unsigned long)wake_verifier_last_us()
#else
      0UL, 0UL, 0UL, 0UL, 0UL
#endif
          ,
      (unsigned long)pikoo::coalesced_frames(),
      (unsigned long)pikoo::frame_write_errors(),
      (unsigned long)transport_stop_max_us.load(),
      unsigned(uxQueueMessagesWaiting(upload_queue)),
      (unsigned long)session_steps.load(), (unsigned long)tx_holds.load(),
      unsigned(sender_handle ? uxTaskGetStackHighWaterMark(sender_handle) : 0),
      wake_model_identity(), wake_policy_identity());
}
void controls_task(void *) {
  pikoo::Button button;
  char command[32]{};
  size_t used = 0;
  // ESP32-S3 can boot normally after a USJ control-line reset while its USB
  // peripheral stops responding (esp-idf#18996). Reattach once on startup,
  // before installing its driver, so recovery does not require a power cycle.
  // The host sees a brief disconnect; flash, NVS and the CPU are unchanged.
  const usb_serial_jtag_pull_override_vals_t detached{};
  usb_serial_jtag_ll_phy_enable_pull_override(&detached);
  vTaskDelay(pdMS_TO_TICKS(500));
  PERIPH_RCC_ATOMIC() { usb_serial_jtag_ll_reset_register(); }
  usb_serial_jtag_driver_config_t usb{};
  usb.tx_buffer_size = 2048;
  usb.rx_buffer_size = 256;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
  // Share the installed driver's FIFO ownership with stdout. The default
  // console writes directly to the hardware and busy-waits for large exports.
  usb_serial_jtag_vfs_use_driver();
  uint64_t report = 0, last_tone = 0;
  enum class Transfer { None, Credentials, Import };
  Transfer transfer = Transfer::None;
  std::string payload;
  uint64_t transfer_deadline = 0;
  bool too_long = false, command_overflow = false;
  while (true) {
    control_action(button.update(!gpio_get_level(board::Button), now()));
    uint8_t c;
    for (unsigned read = 0;
         read < 256 && usb_serial_jtag_read_bytes(&c, 1, 0) == 1; ++read) {
      const bool usb_safe = muted && !awake && visual_state == State::Muted;
      if (transfer != Transfer::None) {
        if (c == '\r' && payload.empty())
          continue;
        if (c == '\n') {
          bool ok = false;
          if (usb_safe && !too_long && now() <= transfer_deadline) {
            if (transfer == Transfer::Credentials)
              ok = pikoo::provision_agent(payload);
            else {
              pikoo::FamilyStore imported(pikoo::write_family_snapshot);
              ok = pikoo::init_family_store(imported) &&
                   pikoo::import_family_snapshot(imported, payload);
            }
          }
          mbedtls_platform_zeroize(payload.data(), payload.size());
          payload.clear();
          transfer = Transfer::None;
          ESP_LOGI("pikoo", "agent usb result=%s",
                   ok ? "ok_reboot" : "rejected");
        } else if (c != '\r') {
          const auto limit = transfer == Transfer::Credentials
                                 ? pikoo::AgentConfig::Limit
                                 : pikoo::FamilyStore::Capacity;
          if (payload.size() < limit && now() <= transfer_deadline && usb_safe)
            payload.push_back(char(c));
          else
            too_long = true;
        }
        continue;
      }
      if (c == '\r' || c == '\n') {
        if (command_overflow) {
          command_overflow = false;
          used = 0;
          continue;
        }
        command[used] = 0;
        int requested_db = 0;
        if (!strcmp(command, "status"))
          diagnostics();
        else if (usb_safe && (!strcmp(command, "agent provision") ||
                              !strcmp(command, "agent import"))) {
          transfer = !strcmp(command, "agent provision") ? Transfer::Credentials
                                                         : Transfer::Import;
          too_long = false;
          transfer_deadline = now() + 30000;
          ESP_LOGI("pikoo", "agent usb ready");
        } else if (usb_safe && !strcmp(command, "agent reboot")) {
          ESP_LOGI("pikoo", "agent usb result=ok_reboot");
          vTaskDelay(pdMS_TO_TICKS(200));
          esp_restart();
        } else if (usb_safe && !strcmp(command, "agent export")) {
          pikoo::FamilyStore exported(pikoo::write_family_snapshot);
          if (pikoo::init_family_store(exported)) {
            auto snapshot = exported.snapshot();
            printf("PIKOO_AGENT_SNAPSHOT %s\n", snapshot.c_str());
          } else
            ESP_LOGI("pikoo", "agent usb result=rejected");
        } else if (usb_safe && !strcmp(command, "agent forget")) {
          const bool ok = pikoo::forget_agent_credentials();
          ESP_LOGI("pikoo", "agent usb result=%s",
                   ok ? "ok_reboot" : "rejected");
        } else if (!config_ready) {
          if (!strcmp(command, "status"))
            diagnostics();
          else if (!strcmp(command, "mute")) {
            muted = true;
            session.mute();
            publish_state();
          } else
            ESP_LOGW("pikoo", "USB configuration required");
        } else if (!strcmp(command, "eyes freeze")) {
          display_pause_until = now() + 120000;
          ESP_LOGI("diag", "eyes_frozen=1 duration_ms=120000");
        } else if (!strcmp(command, "eyes resume")) {
          display_pause_until = 0;
          ESP_LOGI("diag", "eyes_frozen=0");
        }
        // Enter only after the session task has published a fully muted state,
        // so a concurrent wake cannot race the test's network-isolation gate.
        else if (!strcmp(command, "wake test on") && muted && !awake &&
                 !uploading && visual_state == State::Muted)
          wake_test_until_ms = now() + 300000;
        else if (!strcmp(command, "wake test off"))
          wake_test_until_ms = 0;
        else if (!strcmp(command, "tx hold") && uploading)
          tx_hold_requested = true;
        else if (!strcmp(command, "wake trace") &&
                 visual_state == State::Idle && !muted)
          wake_trace_start();
        else if (!strcmp(command, "wake capture") &&
                 visual_state == State::Idle && !muted)
          wake_capture_start();
        else if (!strcmp(command, "wake"))
          wake_request = true;
        else if (!strcmp(command, "stop")) {
          board::silence();
          cancel_request = true;
        } else if (!strcmp(command, "end")) {
          board::silence();
          gate_off();
          finish_request = true;
          stop_request = true;
        } else if (!strcmp(command, "mute")) {
          muted = true;
          gate_off();
          board::silence();
          if (config_ready)
            board::capture_enabled(false);
          stop_request = true;
        } else if (!strcmp(command, "unmute")) {
          muted = false;
          if (config_ready)
            board::capture_enabled(true);
          stop_request = true;
        } else if (!strcmp(command, "tone") && visual_state == State::Idle &&
                 now() - last_tone > 5000) {
          last_tone = now();
          diagnostic_tone = true;
        } else if (!strcmp(command, "volume low"))
          board::set_volume(-36);
        else if (!strcmp(command, "volume normal"))
          board::set_volume(-24);
        else if (!strcmp(command, "volume higher"))
          board::set_volume(-12);
        else if (!strcmp(command, "volume louder"))
          board::set_volume(-6);
        else if (!strcmp(command, "volume full"))
          board::set_volume(0);
        else if (pikoo::volume_command(command, requested_db)) {
          const auto result = board::set_volume(requested_db);
          if (result == ESP_OK)
            ESP_LOGI("audio", "volume_db=%d dac_reg=%d", board::volume_db(),
                     board::volume_register());
          else
            ESP_LOGW("audio", "Volume update failed: %s",
                     esp_err_to_name(result));
        } else if (!strcmp(command, "rotate 90") ||
                   !strcmp(command, "rotate 270")) {
          int angle = !strcmp(command, "rotate 90") ? 90 : 270;
          board::display_rotation(angle);
          nvs_handle_t n;
          if (nvs_open("pikoo", NVS_READWRITE, &n) == ESP_OK) {
            nvs_set_i32(n, "rotation", angle);
            nvs_commit(n);
            nvs_close(n);
          }
        }
        used = 0;
      } else if (used < sizeof(command) - 1 && !command_overflow)
        command[used++] = c;
      else
        command_overflow = true;
    }
    if (now() - report >= 10000) {
      report = now();
      diagnostics();
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
void sender_task(void *) {
  pikoo::LiveUpload24k upsample;
  uint32_t resample_epoch = UINT32_MAX;
  std::vector<int16_t> upsampled(
      agent_config.audio_rate == 24000 ? upload_samples * 3 / 2 : 0);
  while (true) {
    // Explicit USB-only fault injection. Never enabled by normal interaction.
    if (tx_hold_requested.exchange(false) && tx_enabled) {
      ++tx_holds;
      ESP_LOGI("diag", "controlled TX hold begin ms=1500");
      vTaskDelay(pdMS_TO_TICKS(1500));
      ESP_LOGI("diag", "controlled TX hold end");
    }
    // Control/cancel/heartbeat events precede the next microphone packet.
    for (int i = 0; i < 2; ++i) {
      ControlMessage message;
      {
        std::lock_guard<std::mutex> lock(tx_mutex);
        if (control_queue.empty())
          break;
        message = std::move(control_queue.front());
        control_queue.pop_front();
      }
      send_wire(message.json, message.connection);
    }
    Upload u;
    if (tx_enabled && uploading &&
        xQueueReceive(upload_queue, &u, 0) == pdTRUE &&
        u.epoch == stream_epoch) {
      const auto connection = connection_epoch.load();
      auto o = event("session.input_audio.append");
      const int16_t *pcm = u.pcm;
      size_t samples = u.count;
      if (agent_config.audio_rate == 24000) {
        if (resample_epoch != u.epoch) {
          upsample.reset();
          resample_epoch = u.epoch;
        }
        samples = upsample.convert(u.pcm, u.count, upsampled.data());
        if (!samples) {
          fail_queue(4);
          continue;
        }
        pcm = upsampled.data();
      }
      auto audio = encode(pcm, samples * 2);
      cJSON_AddStringToObject(o, "audio", audio.c_str());
      send_wire(stringify(o), connection, u.epoch, u.count);
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}
void session_task(void *) {
  while (true) {
    ++session_steps;
    if (tone_complete.exchange(false) && active && session.ready && !muted &&
        !interaction.closing())
      uploading = true;
    if (stop_request.exchange(false)) {
      end_socket();
      interaction.reset();
      if (finish_request.exchange(false)) {
        if (agent_ready)
          family.clear_context();
      }
      muted ? session.mute() : session.stop();
      next_retry = 0;
    }

#ifdef PIKOO_WAKE_VETO
    if (verified_wake_request.exchange(false) &&
        verified_wake_epoch == stream_epoch && !muted && !active &&
        session.state != State::AuthError) {
      wake_mark_confirmed();
      wake_request = true;
    }
#endif
    if (wake_request.exchange(false) && !muted && !active &&
        session.state != State::AuthError) {
      next_retry = 0;
      interaction.wake();
      begin();
    }
    if (cancel_request.exchange(false) && active)
      begin();
    if (net_open.exchange(false))
      agent.start(now(), interaction.greeting_pending(),
                  agent_config.audio_rate);
    if (overflow.exchange(false) && active) {
      net_down = true;
      ESP_LOGW("pikoo", "bounded queue overflow reason=%d send_us=%lu queue=%u",
               overflow_reason.load(), (unsigned long)send_last_us.load(),
               unsigned(uxQueueMessagesWaiting(upload_queue)));
    }
    if (net_down.exchange(false) && active) {
      int code = close_code;
      bool farewell = interaction.closing();
      end_socket();
      session.ready = false;
      if (farewell) {
        interaction.reset();
        session.stop();
        next_retry = 0;
        ESP_LOGI("pikoo", "farewell disconnected; standby");
      } else if (code == 4003)
        session.state = State::AuthError;
      else {
        session.state = State::Offline;
        next_retry =
            now() +
            (code == 429
                 ? 60000
                 : std::min<unsigned>(
                       30000, 1000u << std::min<unsigned>(retries++, 5))) +
            esp_random() % 500;
      }
    }
    if (next_retry && now() >= next_retry && wifi_ready && !muted) {
      next_retry = 0;
      begin();
    }
    if (active && session.ready && now() - connecting_at > 30000)
      retries = 0;
    if (active && session.state == State::Connecting &&
        now() - connecting_at > 30000)
      net_down = true;
    // A burst of downstream speech must not postpone microphone upload until
    // the entire receive backlog has been decoded.
    std::string message;
    pikoo::pump_bounded(
        2,
        [&] {
          std::lock_guard<std::mutex> lock(in_mutex);
          if (incoming.empty())
            return false;
          message = std::move(incoming.front());
          incoming.pop_front();
          return true;
        },
        [&] {
          auto started = esp_timer_get_time();
          agent.receive(message, now());
          receive_max_us = std::max(receive_max_us.load(),
                                    uint32_t(esp_timer_get_time() - started));
        });
    {
      std::deque<std::string> receipts;
      {
        std::lock_guard<std::mutex> lock(out_mutex);
        receipts.swap(outgoing);
      }
      for (auto &s : receipts) {
        auto r = cJSON_Parse(s.c_str());
        if (r) {
          cJSON_Delete(r);
          session.last_activity = now();
        }
      }
    }
    session.last_activity = std::max(session.last_activity, speech_at.load());
    if (session.ready)
      session.state =
          board::output_level() > .003f ? State::Speaking : State::Listening;
    {
      std::deque<pikoo::HttpResult> results;
      {
        std::lock_guard<std::mutex> lock(backend_mutex);
        results.swap(backend_results);
      }
      for (const auto &result : results)
        backend.complete(result, now());
    }
    backend.tick(now());
    backend_token = backend.token();
    backend_scope = backend.scope();
    bool playing;
    {
      std::lock_guard<std::mutex> l(play_mutex);
      playing = playback.in_flight() &&
                ((local_audio_at && now() - local_audio_at < 2000) ||
                 board::output_level() > .003f);
    }
    if (!continuous_audio && session.ready && !playing &&
        session.state == State::Speaking) {
      session.state = State::Listening;
    }
    if (active) {
      agent.tick(now());
      if (agent.sleep_due(now(), playing)) {
        end_socket();
        interaction.reset();
        next_retry = 0;
        session.stop();
      }
    }
    publish_state();
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
} // namespace
extern "C" void app_main() {
  // Keep decoded audio and graphics allocations out of scarce internal RAM.
  heap_caps_malloc_extmem_enable(512);
  // cJSON nodes are smaller than the general external-allocation threshold.
  // Keep backend response trees out of the internal heap needed by Wi-Fi,
  // TLS and audio DMA. Install once, before any application task starts;
  // heap_caps_free also accepts objects allocated before these hooks.
  cJSON_Hooks json_hooks{
      [](size_t size) -> void * {
        return heap_caps_malloc_prefer(
            size, 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
            MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
      },
      heap_caps_free};
  cJSON_InitHooks(&json_hooks);
  vTaskPrioritySet(nullptr, 5);
  ESP_ERROR_CHECK(nvs_flash_init());
  // FreeRTOS dynamic queue storage uses internal RAM, even when ordinary
  // malloc prefers PSRAM. Reserve internal RAM for Wi-Fi/TLS and DMA instead.
  static StaticQueue_t upload_queue_state;
  auto upload_storage = static_cast<uint8_t *>(heap_caps_malloc(
      upload_slots * sizeof(Upload), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  configASSERT(upload_storage);
  upload_queue = xQueueCreateStatic(upload_slots, sizeof(Upload),
                                    upload_storage, &upload_queue_state);
  wake_queue = xQueueCreate(4, sizeof(LocalWakeAudio));
  configASSERT(upload_queue && wake_queue);
  boot_id = esp_random();
  gpio_config_t button_cfg{};
  button_cfg.pin_bit_mask = 1ULL << board::Button;
  button_cfg.mode = GPIO_MODE_INPUT;
  button_cfg.pull_up_en = GPIO_PULLUP_ENABLE;
  ESP_ERROR_CHECK(gpio_config(&button_cfg));
  ESP_ERROR_CHECK(board::display_init());
  display_ready = true;
  // Keep low-priority rendering away from Wi-Fi/AFE on core 0. Sleeping
  // frames use a clipped redraw so inference/audio remain higher priority.
  xTaskCreatePinnedToCore(graphics_task, "eyes", 8192, nullptr, 2, nullptr, 1);
  xTaskCreatePinnedToCore(controls_task, "controls", 4096, nullptr, 9, nullptr,
                          0);
  nvs_handle_t nvs;
  if (nvs_open("pikoo", NVS_READONLY, &nvs) == ESP_OK) {
    int32_t rotation = 90;
    nvs_get_i32(nvs, "rotation", &rotation);
    board::display_rotation(rotation);
    nvs_close(nvs);
  }
  esp_log_level_set("transport_ws", ESP_LOG_NONE);
  esp_log_level_set("websocket_client", ESP_LOG_NONE);
  agent_ready = pikoo::load_agent_config(agent_config) &&
                      pikoo::init_family_store(family);
  if (!agent_ready) {
    muted = true;
    session.mute();
    publish_state();
    ESP_LOGW("pikoo", "USB configuration required");
    return;
  }
  agent.configure(agent_config);
  backend.configure(agent_config);
  ssid = agent_config.ssid;
  password = agent_config.password;
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  char id[48];
  snprintf(id, sizeof(id), "pikoo-%02x%02x%02x%02x%02x%02x", mac[0], mac[1],
           mac[2], mac[3], mac[4], mac[5]);
  device_id = id;
  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  esp_netif_create_default_wifi_sta();
  wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&init));
  ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
  esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED,
                             wifi_event, nullptr);
  esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event,
                             nullptr);
  wifi_config_t config{};
  memcpy(config.sta.ssid, ssid.data(), ssid.size());
  memcpy(config.sta.password, password.data(), password.size());
  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
  ESP_ERROR_CHECK(esp_wifi_start());
  esp_wifi_set_ps(WIFI_PS_NONE);
  esp_wifi_connect();
  esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
  esp_sntp_setservername(0, const_cast<char *>("time.cloudflare.com"));
  esp_sntp_setservername(1, const_cast<char *>("pool.ntp.org"));
  esp_sntp_init();
  ESP_ERROR_CHECK(board::audio_init());
  config_ready = true;
  if (muted)
    board::capture_enabled(false);
  auto afe_config =
      afe_config_init("MR", nullptr, AFE_TYPE_FD, AFE_MODE_LOW_COST);
  afe_config->wakenet_init = false;
  afe_config->vad_model_name = nullptr;
  afe_config->vad_init = true;
  afe_config->aec_init = true;
  afe_config->aec_mode = AEC_MODE_FD_LOW_COST;
  afe_config->vad_mute_playback = false;
  // FD already performs nonlinear echo suppression. An additional WebRTC NS
  // stage is discouraged by ESP-SR's config check for recognition input.
  afe_config->ns_init = false;
  afe_config->afe_ns_mode = AFE_NS_MODE_WEBRTC;
  afe_config->memory_alloc_mode = AFE_MEMORY_ALLOC_MORE_PSRAM;
  afe_config->afe_perferred_core = 0;
  afe_config->afe_perferred_priority = 7;
  ESP_LOGI("pikoo", "AEC type=%d mode=%d filter=%d nlp=%d",
           int(afe_config->afe_type), int(afe_config->aec_mode),
           afe_config->aec_filter_length, int(afe_config->aec_nlp_level));
  afe = esp_afe_handle_from_config(afe_config);
  afe_data = afe->create_from_config(afe_config);
  afe_config_free(afe_config);
  assert(afe_data);
  ESP_LOGI("pikoo", "AFE feed=%d fetch=%d channels=%d",
           afe->get_feed_chunksize(afe_data),
           afe->get_fetch_chunksize(afe_data),
           afe->get_feed_channel_num(afe_data));
  if (!wake_init())
    ESP_LOGE("pikoo", "wake initialization failed; button fallback available; "
                      "acceptance blocked");
#ifdef PIKOO_WAKE_VETO
  if (!wake_verifier_init())
    ESP_LOGE(
        "pikoo",
        "verifier unavailable; voice wake disabled, BOOT fallback available");
#endif
  xTaskCreatePinnedToCore(capture_task, "capture", 8192, nullptr, 8,
                          &capture_handle, 0);
  xTaskCreatePinnedToCore(processing_task, "audio-process", 12288, nullptr, 6,
                          &process_handle, 1);
  // AFE and Wi-Fi consume core 0. Keep 10 ms playback blocks on core 1;
  // I2S waits yield CPU to the bounded network loop between blocks.
  xTaskCreatePinnedToCore(playback_task, "playback", 8192, nullptr, 6,
                          &playback_handle, 1);

  xTaskCreatePinnedToCore(backend_task, "backend", 12288, nullptr, 3, &backend_handle,
                          1);
  xTaskCreatePinnedToCore(session_task, "session", 12288, nullptr, 5, nullptr,
                          1);
  xTaskCreatePinnedToCore(sender_task, "sender", 8192, nullptr, 5,
                          &sender_handle, 1);
}
