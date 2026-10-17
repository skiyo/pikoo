#include "board_audio.hpp"
#include "board.hpp"
#include "pikoo_button.hpp"
#include "driver/usb_serial_jtag.h"
#include "esp_app_desc.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
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
#include "esp_transport_ssl.h"
#include "esp_transport_ws.h"
#include "lwip/sockets.h"
#include "lwip/tcp.h"
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
#include <set>
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
    net_down{false}, overflow{false}, tone_request{false}, tone_complete{false},
    diagnostic_tone{false}, display_ready{false}, config_ready{false}, finish_request{false};
std::atomic<int> close_code{0}, overflow_reason{0};
std::atomic<uint32_t> send_max_us{0},send_last_us{0};
std::atomic<uint32_t> resample_max_us{0},receive_max_us{0};
std::atomic<uint32_t> playback_gaps{0},playback_gap_max_us{0};
void fail_queue(int reason){overflow_reason=reason;overflow=true;}
std::atomic<uint64_t> speech_at{0};
std::atomic<uint32_t> stream_epoch{0};
// 40 ms of PCM plus Base64/JSON fits inside one 4096-byte TLS record.
// Keep the same 800 ms bounded backlog as the previous eight 100 ms packets.
constexpr size_t upload_samples=640;
constexpr unsigned upload_slots=20;
static_assert(4*((upload_samples*2+2)/3)+512<4096);
struct Upload {
  uint32_t epoch;
  int count;
  int16_t pcm[upload_samples];
};
QueueHandle_t upload_queue;
esp_websocket_client_handle_t ws = nullptr;
esp_transport_handle_t tls_transport=nullptr,websocket_transport=nullptr;
std::string endpoint, token, ssid, password, device_id, ws_uri, headers,
    fragment;
uint64_t next_retry = 0, connecting_at = 0;
unsigned retries = 0;
uint32_t serial = 0;
bool active = false, takeover = false;
std::atomic<State> visual_state{State::Idle};
std::string conversation_id;
int64_t conversation_at=0;
std::atomic<uint32_t> upload_count{0}, reconnect_count{0};
std::atomic<uint32_t> received_audio_count{0};
std::atomic<uint32_t> captured_samples{0},processed_samples{0},uploaded_samples{0};
std::atomic<float> processed_level{0};
uint32_t boot_id;
TaskHandle_t capture_handle=nullptr, process_handle=nullptr, playback_handle=nullptr;
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
  snprintf(id, sizeof(id), "%s-%08lx-%lu", device_id.c_str(),
           static_cast<unsigned long>(boot_id),
           static_cast<unsigned long>(++serial));
  cJSON_AddStringToObject(o, "event_id", id);
  return o;
}
bool send(cJSON *o) {
  auto s = stringify(o);
  if (ws && esp_websocket_client_is_connected(ws)) {
    auto started=esp_timer_get_time();
    int sent=esp_websocket_client_send_text(ws,s.data(),s.size(),pdMS_TO_TICKS(1000));
    auto elapsed=static_cast<uint32_t>(esp_timer_get_time()-started);send_last_us=elapsed;send_max_us=std::max(send_max_us.load(),elapsed);
    if(sent==int(s.size()))return true;
    net_down=true;
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
  board::silence();
  tone_request = false;
  tone_complete = false;
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
  if(websocket_transport){esp_transport_destroy(websocket_transport);websocket_transport=nullptr;}
  if(tls_transport){esp_transport_destroy(tls_transport);tls_transport=nullptr;}
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
    int fd=esp_transport_get_socket(tls_transport),enabled=1;
    int result=setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&enabled,sizeof(enabled));
    ESP_LOGI("pikoo","low latency socket configured=%d",result==0);
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
void forget_conversation() {
  conversation_id.clear(); conversation_at=0;
  nvs_handle_t n;
  if(nvs_open("pikoo",NVS_READWRITE,&n)==ESP_OK){nvs_erase_key(n,"conversation");nvs_erase_key(n,"conv_at");nvs_commit(n);nvs_close(n);}
}
void ensure_conversation() {
  auto t=static_cast<int64_t>(time(nullptr));
  if(!conversation_id.empty() && t>=conversation_at && t-conversation_at<86400) return;
  conversation_id="esp32-"+device_id+"-"+std::to_string(esp_random())+"-"+std::to_string(esp_random());
  conversation_at=t;
  nvs_handle_t n;
  if(nvs_open("pikoo",NVS_READWRITE,&n)==ESP_OK){nvs_set_str(n,"conversation",conversation_id.c_str());nvs_set_i64(n,"conv_at",t);nvs_commit(n);nvs_close(n);}
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
  ensure_conversation();
  ++reconnect_count;
  ws_uri = endpoint + "?sessionId=" + conversation_id;
  headers = "Authorization: Bearer " + token + "\r\n";
  // The public external-transport API exposes the owned TLS socket, allowing
  // TCP_NODELAY. Otherwise split WS header/payload writes can stall on Nagle.
  tls_transport=esp_transport_ssl_init();
  if(!tls_transport){net_down=true;return;}
  esp_transport_ssl_crt_bundle_attach(tls_transport,esp_crt_bundle_attach);
  esp_transport_set_default_port(tls_transport,443);
  websocket_transport=esp_transport_ws_init(tls_transport);
  if(!websocket_transport){net_down=true;return;}
  esp_transport_set_default_port(websocket_transport,443);
  auto path=ws_uri.substr(ws_uri.find('/',6));
  esp_transport_ws_config_t transport_config{};
  transport_config.ws_path=path.c_str();transport_config.headers=headers.c_str();
  transport_config.propagate_control_frames=true;
  if(esp_transport_ws_set_config(websocket_transport,&transport_config)!=ESP_OK){net_down=true;return;}
  esp_websocket_client_config_t cfg{};
  cfg.uri = ws_uri.c_str();
  cfg.headers = headers.c_str();
  cfg.ext_transport=websocket_transport;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.disable_auto_reconnect = true;
  cfg.buffer_size = 8192;
  cfg.task_stack = 8192;
  cfg.task_core_id_set=true;cfg.task_core_id=1;cfg.task_prio=5;
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
  static std::set<std::string> seen;
  if(seen.size()<40 && seen.insert(type).second)ESP_LOGI("pikoo","event type=%s",type.c_str());
  if (type == "session.ping") {
    auto response = event("session.pong");
    cJSON_AddStringToObject(response, "request_event_id",
                            field(o, "event_id").c_str());
    send(response);
  } else if (type == "voice.ready" && active && !muted) {
    auto rate = cJSON_GetObjectItem(o, "inputSampleRate");
    if (!cJSON_IsNumber(rate) || rate->valueint != 16000) {
      fail_queue(4);
    } else {
      session.voice_ready(now());
      tone_request = true;
      // Playback task opens upload only after the ready tone has drained.
      // Reset retry backoff only after a stable connection, not mere readiness.
    }
  } else if (type == "audio.delta" && session.ready && !muted) {
    ++received_audio_count;
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
        static std::string logged_id;
        static unsigned logged_chunks=0;
        if(logged_id!=id){logged_id=id;logged_chunks=0;}
        std::lock_guard<std::mutex> lock(play_mutex);
        if (!playback.rejected(id) &&
            !playback.append(id, pcm.data(), size / 2))
          fail_queue(5);
        if(logged_chunks++<6)ESP_LOGI("pikoo","audio rx chunk=%u samples=%u queued=%u",logged_chunks,unsigned(size/2),unsigned(playback.queued()));
        session.last_activity = now();
        session.state = State::Speaking;
      }
    }
  } else if (type == "session.ready") {
    ESP_LOGI("pikoo","gateway ready");
  } else if (type == "error" || type == "voice.error") {
    auto code=field(o,"code");
    if(code.empty())code=field(cJSON_GetObjectItem(o,"error"),"code");
    ESP_LOGW("pikoo","gateway error code=%s",code.substr(0,80).c_str());
  } else if (type == "response.started") {
    ESP_LOGI("pikoo","audio response announced");
    std::lock_guard<std::mutex> lock(play_mutex);
    if (session.ready)
      playback.announce(id);
    else
      playback.reject(id);
  } else if (type == "voice.state" && field(o, "state") == "processing" &&
             session.ready) {
    session.state = State::Thinking;
  } else if (type == "audio.done") {
    ESP_LOGI("pikoo","audio response complete");
    std::lock_guard<std::mutex> lock(play_mutex);
    playback.done(id);
  } else if (type == "playback.clear") {
    ESP_LOGI("pikoo","audio playback clear");
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
  int64_t last_block=0;
  unsigned logged_gaps=0;
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
      auto epoch=board::generation();
      if(board::play(tone.data(),1280,epoch)) {board::drain();if(epoch==board::generation()) tone_complete=true;}
    }
    if(diagnostic_tone.exchange(false)) {
      std::vector<int16_t> tone(2880);auto epoch=board::generation();
      for(int frequency:{700,1000}) {
        for(int i=0;i<2880;i++)tone[i]=1800*std::min(1.f,std::min(i/160.f,(2879-i)/160.f))*std::sin(2*M_PI*frequency*i/16000);
        if(!board::play(tone.data(),2880,epoch))break;
        board::drain();vTaskDelay(pdMS_TO_TICKS(100));
      }
      board::silence();
      ESP_LOGI("diag","short tone finished; mic_peak=%.5f ref_peak=%.5f playback_stack_free=%u; human sound/heat check required",board::microphone_peak(),board::reference_peak(),unsigned(uxTaskGetStackHighWaterMark(nullptr)));
    }
    const bool keep_output_ready=awake.load()&&!muted.load();
    if(keep_output_ready)board::prepare_playback(board::generation());
    board::playback_idle(keep_output_ready);
    pikoo::Playback::Chunk chunk;
    bool have = false, started = false;
    {
      std::lock_guard<std::mutex> lock(play_mutex);
      have = playback.take(chunk,24000*500/1000,now(),600);
      if (have)
        started = playback.started(chunk);
    }
    if (have) {
      if (current != chunk.epoch || response != chunk.id) {
        converter.reset();
        current = chunk.epoch;
        response = chunk.id;
        last_block=0;logged_gaps=0;
      }
      const auto generation = board::generation();
      {
        std::lock_guard<std::mutex> lock(play_mutex);
        if (chunk.epoch != playback.epoch())
          continue;
      }
      // Convert only 10 ms at a time. Converting a whole server chunk before
      // feeding I2S creates a silence gap whenever it exceeds the DMA depth.
      bool played=true;
      for(size_t pos=0;pos<chunk.pcm.size();pos+=240) {
        auto entered=esp_timer_get_time();
        if(last_block&&entered-last_block>45000){
          auto gap=uint32_t(entered-last_block);++playback_gaps;playback_gap_max_us=std::max(playback_gap_max_us.load(),gap);
          if(logged_gaps++<5)ESP_LOGW("pikoo","audio supply gap us=%lu",(unsigned long)gap);
        }
        auto conversion_started=esp_timer_get_time();
        auto output=converter.process(chunk.pcm.data()+pos,std::min<size_t>(240,chunk.pcm.size()-pos));
        resample_max_us=std::max(resample_max_us.load(),uint32_t(esp_timer_get_time()-conversion_started));
        if(!board::play(output.data(),output.size(),generation)){played=false;break;}
        last_block=esp_timer_get_time();
        if(started){ESP_LOGI("pikoo","audio first block queued samples=%u",unsigned(chunk.pcm.size()));receipt("playback.started",chunk.id);started=false;}
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
  while (true) {
    if (board::capture(pcm.data(), count)) {
      captured_samples+=count;
      afe->feed(afe_data, pcm.data());
    } else
      vTaskDelay(pdMS_TO_TICKS(10));
  }
}
void processing_task(void *) {
  bool was_awake = true;
  std::vector<int16_t> packet(upload_samples);
  size_t used=0;uint32_t packet_epoch=0;
  while (true) {
    auto r = afe->fetch_with_delay(afe_data,pdMS_TO_TICKS(100));
    if (!r || r->ret_value != ESP_OK)
      continue;
    size_t samples=r->data_size/2;
    processed_samples+=samples;
    float power=0;for(size_t j=0;j<samples;j++)power+=float(r->data[j])*r->data[j];
    processed_level=samples?std::sqrt(power/samples)/32768.f:0;
    const bool a = awake;
    const auto epoch = stream_epoch.load();
    if (muted) {
      used=0;
      continue;
    }
    if (!a) {
      if (was_awake)
        wake_reset();
      if (wake_feed(r->data, r->data_size / 2))
        wake_request = true;
    }
    was_awake = a;
    if (uploading) {
      if (r->vad_state == VAD_SPEECH && board::microphone_level()>.001f)
        speech_at = now();
      if(packet_epoch!=epoch){used=0;packet_epoch=epoch;}
      size_t pos=0;
      while(pos<samples) {
        size_t n=std::min<size_t>(upload_samples-used,samples-pos);
        memcpy(packet.data()+used,r->data+pos,n*2);used+=n;pos+=n;
        if(used==upload_samples) {
          Upload u{};u.epoch=epoch;u.count=upload_samples;memcpy(u.pcm,packet.data(),upload_samples*sizeof(int16_t));used=0;
          if(!xQueueSend(upload_queue,&u,0))fail_queue(8);
        }
      }
    } else used=0;
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
void publish_state(){visual_state=session.state;}
void graphics_task(void *) {
  pikoo::eyes::Animator animator;
  while(true) {
    auto started=now(); auto state=visual_state.load();
    pikoo::eyes::Input input{};input.state=static_cast<pikoo::eyes::State>(int(state)+1);
    // Eyes has Boot first, followed by the same nine Session states.
    input.time_ms=started;input.level=std::min(1.f,(state==State::Speaking?board::output_level():board::microphone_level())*8);
    const char *label="";
    if(!config_ready) {input.state=pikoo::eyes::State::Boot;label="USB SETUP";}
    else if(state==State::Muted) label="MIC OFF";
    else if(state==State::Offline)label="OFFLINE";
    else if(state==State::Occupied)label="HOLD TO TAKE";
    else if(state==State::AuthError)label="PAIR AGAIN";
    if(display_ready) board::display_frame(animator.update(input),label);
    auto elapsed=now()-started;vTaskDelay(pdMS_TO_TICKS(elapsed<50?50-elapsed:1));
  }
}
void control_action(pikoo::Button::Action action) {
  if(action==pikoo::Button::Double) {board::silence();gate_off();finish_request=true;stop_request=true;}
  else if(action==pikoo::Button::Press) {
    auto state=visual_state.load();
    if(state==State::Speaking||state==State::Thinking){board::silence();cancel_request=true;}
    else if(state==State::Idle||state==State::Offline) wake_request=true;
  } else if(action==pikoo::Button::Hold) {
    if(visual_state==State::Occupied){takeover_request=true;return;}
    muted=!muted;gate_off();board::silence();board::capture_enabled(!muted);stop_request=true;
  }
}
void diagnostics() {
  wifi_ap_record_t ap{};
  int rssi=esp_wifi_sta_get_ap_info(&ap)==ESP_OK?ap.rssi:0;
  ESP_LOGI("diag","board=%s version=%s state=%d wifi=%d muted=%d upload=%d frames=%lu reconnects=%lu heap=%u min_heap=%u internal=%u psram=%u fps=%.1f mic=%.5f ref=%.5f output=%.5f rx_errors=%lu tx_errors=%lu reset=%d uptime_ms=%llu wake_max_us=%lu wake_calls=%lu capture_stack_free=%u process_stack_free=%u mic_peak=%.5f ref_peak=%.5f received_audio=%lu captured_samples=%lu processed_samples=%lu uploaded_samples=%lu processed_level=%.5f render_us=%lu transfer_us=%lu send_us=%lu send_max_us=%lu resample_max_us=%lu receive_max_us=%lu volume_db=%d dac_reg=%d rssi=%d playback_gaps=%lu playback_gap_max_us=%lu",
    board::Name,esp_app_get_description()->version,int(visual_state.load()),int(wifi_ready.load()),int(muted.load()),int(uploading.load()),
    (unsigned long)upload_count.load(),(unsigned long)reconnect_count.load(),unsigned(esp_get_free_heap_size()),unsigned(esp_get_minimum_free_heap_size()),
    unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),board::display_fps(),board::microphone_level(),board::reference_level(),board::output_level(),
    (unsigned long)board::capture_errors(),(unsigned long)board::playback_errors(),int(esp_reset_reason()),(unsigned long long)now(),
    (unsigned long)wake_max_inference_us(),(unsigned long)wake_inference_count(),
    unsigned(capture_handle?uxTaskGetStackHighWaterMark(capture_handle):0),unsigned(process_handle?uxTaskGetStackHighWaterMark(process_handle):0),
    board::microphone_peak(),board::reference_peak(),(unsigned long)received_audio_count.load(),
    (unsigned long)captured_samples.load(),(unsigned long)processed_samples.load(),(unsigned long)uploaded_samples.load(),processed_level.load(),
    (unsigned long)board::display_render_us(),(unsigned long)board::display_transfer_us(),(unsigned long)send_last_us.load(),(unsigned long)send_max_us.load(),(unsigned long)resample_max_us.load(),(unsigned long)receive_max_us.load(),board::volume_db(),board::volume_register(),rssi,(unsigned long)playback_gaps.load(),(unsigned long)playback_gap_max_us.load());
}
void controls_task(void *) {
  pikoo::Button button;char command[32]{};size_t used=0;
  usb_serial_jtag_driver_config_t usb{};usb.tx_buffer_size=2048;usb.rx_buffer_size=256;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
  uint64_t report=0,last_tone=0;
  while(true) {
    control_action(button.update(!gpio_get_level(board::Button),now()));
    uint8_t c;
    while(usb_serial_jtag_read_bytes(&c,1,0)==1) {
      if(c=='\r'||c=='\n') {
        command[used]=0;
        if(!strcmp(command,"status")) diagnostics();
        else if(!strcmp(command,"wake"))wake_request=true;
        else if(!strcmp(command,"stop")){board::silence();cancel_request=true;}
        else if(!strcmp(command,"end")){board::silence();gate_off();finish_request=true;stop_request=true;}
        else if(!strcmp(command,"mute")){muted=true;gate_off();board::silence();board::capture_enabled(false);stop_request=true;}
        else if(!strcmp(command,"unmute")){muted=false;board::capture_enabled(true);stop_request=true;}
        else if(!strcmp(command,"takeover")&&visual_state==State::Occupied)takeover_request=true;
        else if(!strcmp(command,"tone")&&visual_state==State::Idle&&now()-last_tone>5000){last_tone=now();diagnostic_tone=true;}
        else if(!strcmp(command,"volume low"))board::set_volume(-36);
        else if(!strcmp(command,"volume normal"))board::set_volume(-24);
        else if(!strcmp(command,"volume higher"))board::set_volume(-12);
        else if(!strcmp(command,"volume louder"))board::set_volume(-6);
        else if(!strcmp(command,"rotate 90")||!strcmp(command,"rotate 270")) {
          int angle=!strcmp(command,"rotate 90")?90:270;
          board::display_rotation(angle);nvs_handle_t n;
          if(nvs_open("pikoo",NVS_READWRITE,&n)==ESP_OK){nvs_set_i32(n,"rotation",angle);nvs_commit(n);nvs_close(n);}
        }
        used=0;
      } else if(used<sizeof(command)-1)command[used++]=c;
      else used=0;
    }
    if(now()-report>=10000){report=now();diagnostics();}
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}
void session_task(void *) {
  while (true) {
    if(tone_complete.exchange(false)&&active&&session.ready&&!muted) uploading=true;
    if (stop_request.exchange(false)) {
      end_socket();
      if(finish_request.exchange(false)) forget_conversation();
      muted ? session.mute() : session.stop();
      next_retry = 0;
    }
    if (takeover_request.exchange(false)) {
      takeover = true;
      wake_request = true;
    }
    if (wake_request.exchange(false) && !muted && !active &&
        session.state!=State::AuthError && (session.state!=State::Occupied||takeover)) {
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
    if (overflow.exchange(false) && active) {
      net_down = true;
      ESP_LOGW("pikoo", "bounded queue overflow reason=%d send_us=%lu queue=%u",overflow_reason.load(),(unsigned long)send_last_us.load(),unsigned(uxQueueMessagesWaiting(upload_queue)));
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
    if(active&&session.ready&&now()-connecting_at>30000)retries=0;
    if (active && session.state == State::Connecting &&
        now() - connecting_at > 30000)
      net_down = true;
    // A burst of downstream speech must not postpone microphone upload until
    // the entire receive backlog has been decoded.
    std::string message;
    pikoo::pump_bounded(2,[&]{
      std::lock_guard<std::mutex> lock(in_mutex);
      if(incoming.empty())return false;
      message=std::move(incoming.front());incoming.pop_front();return true;
    },[&]{auto started=esp_timer_get_time();receive(message);receive_max_us=std::max(receive_max_us.load(),uint32_t(esp_timer_get_time()-started));});
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
    pikoo::pump_bounded(2,[&]{return xQueueReceive(upload_queue,&u,0)==pdTRUE;},[&]{
      if (uploading && u.epoch == stream_epoch) {
        auto o = event("input_audio_buffer.append");
        auto audio = encode(u.pcm, u.count * 2);
        cJSON_AddStringToObject(o, "audio", audio.c_str());
        if(send(o)){++upload_count;uploaded_samples+=u.count;}
      }
    });
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
      forget_conversation();
      session.stop();
    }
    publish_state();
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
} // namespace
extern "C" void app_main() {
  // Keep decoded audio and graphics allocations out of scarce internal RAM.
  heap_caps_malloc_extmem_enable(512);
  vTaskPrioritySet(nullptr,5);
  ESP_ERROR_CHECK(nvs_flash_init());
  upload_queue = xQueueCreate(upload_slots, sizeof(Upload));
  boot_id=esp_random();
  gpio_config_t button_cfg{};button_cfg.pin_bit_mask=1ULL<<board::Button;button_cfg.mode=GPIO_MODE_INPUT;button_cfg.pull_up_en=GPIO_PULLUP_ENABLE;
  ESP_ERROR_CHECK(gpio_config(&button_cfg));
  ESP_ERROR_CHECK(board::display_init());display_ready=true;
  xTaskCreatePinnedToCore(graphics_task,"eyes",8192,nullptr,2,nullptr,1);
  nvs_handle_t nvs;
  if (nvs_open("pikoo", NVS_READONLY, &nvs) != ESP_OK) {
    ESP_LOGW("pikoo","USB configuration required");
    return;
  }
  ssid = setting(nvs, "ssid");
  password = setting(nvs, "password");
  endpoint = setting(nvs, "endpoint");
  token = setting(nvs, "token");
  conversation_id=setting(nvs,"conversation");
  nvs_get_i64(nvs,"conv_at",&conversation_at);
  int32_t rotation=90;nvs_get_i32(nvs,"rotation",&rotation);board::display_rotation(rotation);
  nvs_close(nvs);
  if (ssid.empty() || ssid.size() > 32 || password.size() > 63 ||
      endpoint.rfind("wss://", 0) != 0 || token.empty() ||
      token.find_first_of("\r\n") != std::string::npos) {
    ESP_LOGW("pikoo","USB configuration required");
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
  esp_sntp_setservername(0, const_cast<char *>("ntp.aliyun.com"));
  esp_sntp_setservername(1, const_cast<char *>("pool.ntp.org"));
  esp_sntp_init();
  ESP_ERROR_CHECK(board::audio_init());
  config_ready=true;
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
  ESP_LOGI("pikoo","AEC type=%d mode=%d filter=%d nlp=%d",int(afe_config->afe_type),int(afe_config->aec_mode),afe_config->aec_filter_length,int(afe_config->aec_nlp_level));
  afe = esp_afe_handle_from_config(afe_config);
  afe_data = afe->create_from_config(afe_config);
  afe_config_free(afe_config);
  assert(afe_data);
  ESP_LOGI("pikoo","AFE feed=%d fetch=%d channels=%d",afe->get_feed_chunksize(afe_data),afe->get_fetch_chunksize(afe_data),afe->get_feed_channel_num(afe_data));
  if (!wake_init())
    ESP_LOGE("pikoo", "wake initialization failed; button fallback available; acceptance blocked");
  xTaskCreatePinnedToCore(capture_task, "capture", 8192, nullptr, 8, &capture_handle,
                          0);
  xTaskCreatePinnedToCore(processing_task, "audio-process", 12288, nullptr, 6,
                          &process_handle, 1);
  // AFE and Wi-Fi consume core 0. Keep 10 ms playback blocks on core 1;
  // I2S waits yield CPU to the bounded network loop between blocks.
  xTaskCreatePinnedToCore(playback_task, "playback", 8192, nullptr, 6, &playback_handle,1);
  xTaskCreatePinnedToCore(controls_task,"controls",4096,nullptr,9,nullptr,0);
  xTaskCreatePinnedToCore(session_task,"session",12288,nullptr,5,nullptr,1);
}
