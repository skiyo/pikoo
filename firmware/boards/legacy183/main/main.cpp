#include "board_audio.hpp"
#include "bsp/esp32_s3_touch_lcd_1_83.h"
#include "cJSON.h"
#include "esp_afe_sr_models.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_sntp.h"
#include "esp_timer.h"
#include "esp_websocket_client.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "mbedtls/base64.h"
#include "nvs_flash.h"
#include "pikoo_core.hpp"
#include "wake_model.hpp"
#include <atomic>
#include <cstring>
#include <ctime>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace {
using State = pikoo::Session::State;
pikoo::Playback playback;
pikoo::Session session;
std::mutex play_mutex, in_mutex, out_mutex;
std::deque<std::string> incoming, outgoing;
std::atomic<bool> wifi_ready{false}, uploading{false}, awake{false},
    muted{false}, wake_request{false}, stop_request{false},
    cancel_request{false}, takeover_request{false}, net_open{false},
    net_down{false}, overflow{false}, tone_request{false};
std::atomic<int> close_code{0};
std::atomic<uint64_t> speech_at{0};
std::atomic<uint32_t> stream_epoch{0};
struct Upload {
  uint32_t epoch;
  int count;
  int16_t pcm[1024];
};
QueueHandle_t upload_queue;
esp_websocket_client_handle_t ws = nullptr;
std::string endpoint, token, ssid, password, device_id, ws_uri, headers,
    fragment;
uint64_t last_ui = 0, next_retry = 0, connecting_at = 0;
unsigned retries = 0;
uint32_t serial = 0;
bool active = false, takeover = false;
lv_obj_t *status_label, *eyes_label, *mute_button_label, *takeover_button;
const esp_afe_sr_iface_t *afe;
esp_afe_sr_data_t *afe_data;
uint64_t now() { return esp_timer_get_time() / 1000; }
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
  snprintf(id, sizeof(id), "%s-%lu", device_id.c_str(),
           static_cast<unsigned long>(++serial));
  cJSON_AddStringToObject(o, "event_id", id);
  return o;
}
void send(cJSON *o) {
  auto s = stringify(o);
  if (ws && esp_websocket_client_is_connected(ws)) {
    if (esp_websocket_client_send_text(ws, s.data(), s.size(),
                                       pdMS_TO_TICKS(500)) < 0)
      net_down = true;
  }
}
void receipt(const char *type, const std::string &id) {
  std::lock_guard<std::mutex> lock(out_mutex);
  auto o = cJSON_CreateObject();
  cJSON_AddStringToObject(o, "type", type);
  cJSON_AddStringToObject(o, "responseId", id.c_str());
  if (outgoing.size() < 64)
    outgoing.push_back(stringify(o));
  else
    overflow = true;
}
void clear_audio(bool notify) {
  board::silence();
  tone_request = false;
  std::lock_guard<std::mutex> lock(play_mutex);
  for (auto &id : playback.cancel())
    if (notify)
      receipt("playback.cancelled", id);
}
void gate_off() {
  uploading = false;
  ++stream_epoch;
  xQueueReset(upload_queue);
}
void end_socket() {
  gate_off();
  active = false;
  awake = false;
  clear_audio(false);
  if (ws) {
    esp_websocket_client_close(ws, pdMS_TO_TICKS(1000));
    esp_websocket_client_stop(ws);
    esp_websocket_client_destroy(ws);
    ws = nullptr;
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
}
void socket_event(void *, esp_event_base_t, int32_t id, void *data) {
  auto e = static_cast<esp_websocket_event_data_t *>(data);
  if (id == WEBSOCKET_EVENT_CONNECTED) {
    net_open = true;
    return;
  }
  if (id == WEBSOCKET_EVENT_DISCONNECTED || id == WEBSOCKET_EVENT_CLOSED) {
    if (e && e->close_status_code)
      close_code = e->close_status_code;
    net_down = true;
    gate_off();
    board::silence();
    return;
  }
  if (id == WEBSOCKET_EVENT_ERROR) {
    if (e) {
      int status = e->error_handle.esp_ws_handshake_status_code;
      if (status == 401 || status == 403)
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
  if (e->data_len < 0 || fragment.size() + e->data_len > 256 * 1024) {
    overflow = true;
    return;
  }
  fragment.append(e->data_ptr, e->data_len);
  if (e->fin && e->payload_offset + e->data_len == e->payload_len) {
    std::lock_guard<std::mutex> lock(in_mutex);
    if (incoming.size() < 32)
      incoming.push_back(std::move(fragment));
    else
      overflow = true;
    fragment.clear();
  }
}
void begin() {
  if (muted || !wifi_ready || time(nullptr) < 1700000000) {
    session.state = muted ? State::Muted : State::Offline;
    return;
  }
  end_socket();
  close_code = 0;
  session.wake(now());
  active = true;
  awake = true;
  connecting_at = now();
  ws_uri = endpoint + (endpoint.find('?') == std::string::npos ? "?" : "&") +
           "sessionId=esp32-" + device_id + "-" + std::to_string(esp_random());
  headers = "Authorization: Bearer " + token + "\r\n";
  esp_websocket_client_config_t cfg{};
  cfg.uri = ws_uri.c_str();
  cfg.headers = headers.c_str();
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.disable_auto_reconnect = true;
  cfg.buffer_size = 4096;
  cfg.task_stack = 8192;
  cfg.network_timeout_ms = 10000;
  cfg.ping_interval_sec = 20;
  ws = esp_websocket_client_init(&cfg);
  if (!ws) {
    net_down = true;
    return;
  }
  esp_websocket_register_events(ws, WEBSOCKET_EVENT_ANY, socket_event, nullptr);
  esp_websocket_client_start(ws);
}
void hello() {
  auto o = event("session.hello");
  auto protocol = cJSON_AddObjectToObject(o, "protocol");
  cJSON_AddStringToObject(protocol, "min", "7.0.0");
  cJSON_AddStringToObject(protocol, "max", "7.0.0");
  auto client = cJSON_AddObjectToObject(o, "client");
  cJSON_AddStringToObject(client, "type", "esp32");
  cJSON_AddStringToObject(client, "version", "0.1.0");
  cJSON_AddStringToObject(client, "instance_id", device_id.c_str());
  auto caps = cJSON_AddArrayToObject(o, "capabilities");
  for (auto c : {"input.audio", "playback.receipts", "session.heartbeat",
                 "session.takeover"})
    cJSON_AddItemToArray(caps, cJSON_CreateString(c));
  cJSON_AddStringToObject(o, "locale", "zh-CN");
  cJSON_AddStringToObject(o, "time_zone", "Asia/Shanghai");
  auto connection = cJSON_AddObjectToObject(o, "connection");
  for (auto k : {"voice_enabled", "input_enabled", "output_enabled"})
    cJSON_AddBoolToObject(connection, k, true);
  cJSON_AddBoolToObject(connection, "text_only", false);
  cJSON_AddBoolToObject(connection, "takeover", takeover);
  takeover = false;
  send(o);
}
void receive(const std::string &raw) {
  auto o = cJSON_ParseWithLength(raw.data(), raw.size());
  if (!o)
    return;
  auto type = field(o, "type"), id = field(o, "responseId");
  if (type == "session.ping") {
    auto response = event("session.pong");
    cJSON_AddStringToObject(response, "request_event_id",
                            field(o, "event_id").c_str());
    send(response);
  } else if (type == "voice.ready" && active && !muted) {
    auto rate = cJSON_GetObjectItem(o, "inputSampleRate");
    if (!cJSON_IsNumber(rate) || rate->valueint != 16000) {
      overflow = true;
    } else {
      session.voice_ready(now());
      tone_request = true;
      uploading = true;
      retries = 0;
    }
  } else if (type == "audio.delta" && session.ready && !muted) {
    auto rate = cJSON_GetObjectItem(o, "sampleRate");
    auto b64 = field(o, "audio");
    if (cJSON_IsNumber(rate) && rate->valueint == 24000 && !id.empty() &&
        b64.size() <= 192 * 1024) {
      std::vector<int16_t> pcm((b64.size() * 3 / 4 + 4) / 2);
      size_t size = 0;
      if (mbedtls_base64_decode(
              reinterpret_cast<unsigned char *>(pcm.data()), pcm.size() * 2,
              &size, reinterpret_cast<const unsigned char *>(b64.data()),
              b64.size()) == 0 &&
          size % 2 == 0) {
        std::lock_guard<std::mutex> lock(play_mutex);
        if (!playback.rejected(id) &&
            !playback.append(id, pcm.data(), size / 2))
          overflow = true;
        session.last_activity = now();
        session.state = State::Speaking;
      }
    }
  } else if (type == "response.started") {
    std::lock_guard<std::mutex> lock(play_mutex);
    if (session.ready)
      playback.announce(id);
    else
      playback.reject(id);
  } else if (type == "voice.state" && field(o, "state") == "processing" &&
             session.ready) {
    session.state = State::Thinking;
  } else if (type == "audio.done") {
    std::lock_guard<std::mutex> lock(play_mutex);
    playback.done(id);
  } else if (type == "playback.clear") {
    clear_audio(true);
    if (session.ready)
      session.state = State::Listening;
  } else if (type == "transcript.delta" || type == "transcript.final")
    session.last_activity = now();
  cJSON_Delete(o);
}
void playback_task(void *) {
  pikoo::Resampler converter;
  uint32_t current = UINT32_MAX;
  std::string response;
  struct Pending {
    std::string id;
    size_t samples;
    uint32_t epoch;
    uint64_t due;
  };
  std::deque<Pending> pending;
  while (true) {
    if (tone_request.exchange(false)) {
      int16_t tone[1280];
      for (int i = 0; i < 1280; i++)
        tone[i] = 1800 * std::sin(2 * M_PI * 660 * i / 16000);
      board::play(tone, 1280, board::generation());
    }
    pikoo::Playback::Chunk chunk;
    bool have = false, started = false;
    {
      std::lock_guard<std::mutex> lock(play_mutex);
      have = playback.take(chunk);
      if (have)
        started = playback.started(chunk);
    }
    if (have) {
      if (current != chunk.epoch || response != chunk.id) {
        converter.reset();
        current = chunk.epoch;
        response = chunk.id;
      }
      auto output = converter.process(chunk.pcm.data(), chunk.pcm.size());
      const auto generation = board::generation();
      {
        std::lock_guard<std::mutex> lock(play_mutex);
        if (chunk.epoch != playback.epoch())
          continue;
      }
      if (started)
        receipt("playback.started", chunk.id);
      if (board::play(output.data(), output.size(), generation)) {
        pending.push_back(
            {chunk.id, chunk.pcm.size(), chunk.epoch, now() + 50});
      } else if (generation == board::generation())
        overflow = true;
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
        overflow = true;
    }
  }
}
void capture_task(void *) {
  int count = afe->get_feed_chunksize(afe_data);
  std::vector<int16_t> pcm(count * 4);
  while (true) {
    if (board::capture(pcm.data(), count))
      afe->feed(afe_data, pcm.data());
    else
      vTaskDelay(pdMS_TO_TICKS(10));
  }
}
void processing_task(void *) {
  bool was_awake = true;
  while (true) {
    auto r = afe->fetch(afe_data);
    if (!r || r->ret_value != ESP_OK)
      continue;
    const bool a = awake;
    const auto epoch = stream_epoch.load();
    if (muted)
      continue;
    if (!a) {
      if (was_awake)
        wake_reset();
      if (wake_feed(r->data, r->data_size / 2))
        wake_request = true;
    }
    was_awake = a;
    if (uploading) {
      if (r->vad_state == VAD_SPEECH)
        speech_at = now();
      Upload u{};
      u.epoch = epoch;
      u.count = r->data_size / 2;
      if (u.count > 1024) {
        overflow = true;
        continue;
      }
      memcpy(u.pcm, r->data, r->data_size);
      if (!xQueueSend(upload_queue, &u, 0))
        overflow = true;
    }
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
void button(lv_event_t *e) {
  intptr_t command = reinterpret_cast<intptr_t>(lv_event_get_user_data(e));
  if (command == 1)
    wake_request = true;
  else if (command == 2) {
    board::silence();
    cancel_request = true;
  } else if (command == 3) {
    muted = !muted;
    gate_off();
    board::silence();
    stop_request = true;
  } else if (command == 4)
    stop_request = true;
  else if (command == 5)
    takeover_request = true;
}
void ui() {
  bsp_display_start();
  bsp_display_backlight_on();
  bsp_display_lock(0);
  auto screen = lv_screen_active();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x153c35), 0);
  lv_obj_set_style_text_color(screen, lv_color_hex(0xdef4b8), 0);
  lv_obj_set_style_text_font(screen, &lv_font_source_han_sans_sc_16_cjk, 0);
  eyes_label = lv_label_create(screen);
  lv_label_set_text(eyes_label, "-  -");
  lv_obj_set_style_text_font(eyes_label, &lv_font_montserrat_20, 0);
  lv_obj_align(eyes_label, LV_ALIGN_TOP_MID, 0, 30);
  status_label = lv_label_create(screen);
  lv_obj_align(status_label, LV_ALIGN_TOP_MID, 0, 78);
  lv_label_set_text(status_label, "启动中");
  const char *labels[] = {"唤醒", "打断", "静音", "结束", "接管"};
  for (int i = 0; i < 5; i++) {
    auto b = lv_button_create(screen);
    lv_obj_set_size(b, i == 4 ? 204 : 98, 38);
    lv_obj_align(b, LV_ALIGN_TOP_LEFT, 12 + (i % 2) * 108, 118 + (i / 2) * 48);
    auto l = lv_label_create(b);
    lv_label_set_text(l, labels[i]);
    lv_obj_center(l);
    lv_obj_add_event_cb(b, button, LV_EVENT_CLICKED,
                        reinterpret_cast<void *>(intptr_t(i + 1)));
    if (i == 2)
      mute_button_label = l;
    if (i == 4) {
      takeover_button = b;
      lv_obj_add_flag(b, LV_OBJ_FLAG_HIDDEN);
    }
  }
  bsp_display_unlock();
}
void update_ui() {
  if (now() - last_ui < 200)
    return;
  last_ui = now();
  const char *label = "休息中";
  switch (session.state) {
  case State::Connecting:
    label = "连接中";
    break;
  case State::Listening:
    label = "我在听";
    break;
  case State::Thinking:
    label = "想一想";
    break;
  case State::Speaking:
    label = "正在回答";
    break;
  case State::Muted:
    label = "麦克风已关闭";
    break;
  case State::Offline:
    label = "网络未就绪";
    break;
  case State::Occupied:
    label = "其他设备正在使用";
    break;
  case State::AuthError:
    label = "请重新配对";
    break;
  default:
    break;
  }
  if (bsp_display_lock(10)) {
    lv_label_set_text(status_label, label);
    lv_label_set_text(eyes_label, session.state == State::Speaking    ? "^  ^"
                                  : session.state == State::Listening ? "O  O"
                                                                      : "-  -");
    lv_label_set_text(mute_button_label, muted ? "启用" : "静音");
    if (session.state == State::Occupied)
      lv_obj_remove_flag(takeover_button, LV_OBJ_FLAG_HIDDEN);
    else
      lv_obj_add_flag(takeover_button, LV_OBJ_FLAG_HIDDEN);
    bsp_display_unlock();
  }
}
} // namespace
extern "C" void app_main() {
  ESP_ERROR_CHECK(nvs_flash_init());
  upload_queue = xQueueCreate(4, sizeof(Upload));
  ui();
  nvs_handle_t nvs;
  if (nvs_open("pikoo", NVS_READONLY, &nvs) != ESP_OK) {
    bsp_display_lock(0);
    lv_label_set_text(status_label, "请先通过 USB 配置");
    bsp_display_unlock();
    return;
  }
  ssid = setting(nvs, "ssid");
  password = setting(nvs, "password");
  endpoint = setting(nvs, "endpoint");
  token = setting(nvs, "token");
  nvs_close(nvs);
  if (ssid.empty() || ssid.size() > 32 || password.size() > 63 ||
      endpoint.rfind("wss://", 0) != 0 || token.empty() ||
      token.find_first_of("\r\n") != std::string::npos) {
    bsp_display_lock(0);
    lv_label_set_text(status_label, "请先通过 USB 配置");
    bsp_display_unlock();
    return;
  }
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
  esp_sntp_setservername(0, const_cast<char *>("ntp.aliyun.com"));
  esp_sntp_setservername(1, const_cast<char *>("pool.ntp.org"));
  esp_sntp_init();
  ESP_ERROR_CHECK(board::audio_init());
  auto afe_config =
      afe_config_init("MMRN", nullptr, AFE_TYPE_VC, AFE_MODE_LOW_COST);
  afe_config->wakenet_init = false;
  afe_config->vad_model_name = nullptr;
  afe_config->vad_init = true;
  afe_config->aec_init = true;
  afe_config->ns_init = true;
  afe_config->afe_ns_mode = AFE_NS_MODE_WEBRTC;
  afe_config->memory_alloc_mode = AFE_MEMORY_ALLOC_MORE_PSRAM;
  afe = esp_afe_handle_from_config(afe_config);
  afe_data = afe->create_from_config(afe_config);
  afe_config_free(afe_config);
  assert(afe_data);
  if (!wake_init())
    ESP_LOGE("pikoo", "wake initialization failed; touch remains available");
  xTaskCreatePinnedToCore(capture_task, "capture", 4096, nullptr, 8, nullptr,
                          0);
  xTaskCreatePinnedToCore(processing_task, "audio-process", 8192, nullptr, 6,
                          nullptr, 1);
  xTaskCreate(playback_task, "playback", 8192, nullptr, 7, nullptr);
  while (true) {
    if (stop_request.exchange(false)) {
      end_socket();
      muted ? session.mute() : session.stop();
      next_retry = 0;
    }
    if (takeover_request.exchange(false)) {
      takeover = true;
      wake_request = true;
    }
    if (wake_request.exchange(false) && !muted && !active) {
      next_retry = 0;
      begin();
    }
    if (cancel_request.exchange(false) && active) {
      clear_audio(true);
      gate_off();
      send(event("response.cancel"));
      session.ready = false;
      session.state = State::Connecting;
      connecting_at = now();
    }
    if (net_open.exchange(false))
      hello();
    if (overflow.exchange(false)) {
      net_down = true;
      ESP_LOGW("pikoo", "bounded audio/network queue overflow");
    }
    if (net_down.exchange(false) && active) {
      int code = close_code;
      end_socket();
      session.ready = false;
      if (code == 4002 || code == 4001)
        session.state = State::Occupied;
      else if (code == 4003)
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
    if (active && session.state == State::Connecting &&
        now() - connecting_at > 30000)
      net_down = true;
    std::deque<std::string> messages;
    {
      std::lock_guard<std::mutex> lock(in_mutex);
      messages.swap(incoming);
    }
    for (auto &s : messages)
      receive(s);
    {
      std::deque<std::string> receipts;
      {
        std::lock_guard<std::mutex> lock(out_mutex);
        receipts.swap(outgoing);
      }
      for (auto &s : receipts) {
        auto r = cJSON_Parse(s.c_str());
        if (r) {
          auto o = event(field(r, "type").c_str());
          cJSON_AddStringToObject(o, "responseId",
                                  field(r, "responseId").c_str());
          send(o);
          cJSON_Delete(r);
          session.last_activity = now();
        }
      }
    }
    Upload u;
    while (xQueueReceive(upload_queue, &u, 0)) {
      if (uploading && u.epoch == stream_epoch) {
        auto o = event("input_audio_buffer.append");
        auto audio = encode(u.pcm, u.count * 2);
        cJSON_AddStringToObject(o, "audio", audio.c_str());
        send(o);
      }
    }
    session.last_activity = std::max(session.last_activity, speech_at.load());
    bool playing;
    {
      std::lock_guard<std::mutex> l(play_mutex);
      playing = playback.busy();
    }
    if (session.ready && !playing && session.state == State::Speaking) {
      session.state = State::Listening;
    }
    if (session.idle_due(now(), playing)) {
      end_socket();
      session.stop();
    }
    update_ui();
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
