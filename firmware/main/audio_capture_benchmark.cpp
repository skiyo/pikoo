// SPDX-License-Identifier: Apache-2.0
// Private, explicitly authorized acoustic diagnostic. No network initialization.
// Microphone stays disabled until the USB "capture" command; captures <=4.032s.
// PSRAM buffers are exported only after capture and wiped before returning idle.
#include "board_audio.hpp"
#include "esp_afe_sr_models.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "mbedtls/base64.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <vector>

namespace {
constexpr size_t Samples=64000;
const esp_afe_sr_iface_t *afe;
esp_afe_sr_data_t *data;
int16_t *raw,*processed;
std::atomic<bool> active{false},feeding_done{false},fetching_done{false};
std::atomic<size_t> raw_count{0},processed_count{0};
void feed(void *) {
  const int n=afe->get_feed_chunksize(data);
  std::vector<int16_t> pcm(n*2);
  while(true) {
    if(!active){vTaskDelay(pdMS_TO_TICKS(10));continue;}
    if(feeding_done){
      std::fill(pcm.begin(),pcm.end(),0);afe->feed(data,pcm.data());
      vTaskDelay(pdMS_TO_TICKS(32));continue;
    }
    if(!board::capture(pcm.data(),n)){vTaskDelay(pdMS_TO_TICKS(2));continue;}
    const size_t pos=raw_count.load(),take=std::min<size_t>(n,Samples-pos);
    for(size_t i=0;i<take;i++)raw[pos+i]=pcm[2*i];
    raw_count=pos+take;
    afe->feed(data,pcm.data());
    if(raw_count==Samples){board::capture_enabled(false);feeding_done=true;}
  }
}
void fetch(void *) {
  while(true) {
    if(!active||fetching_done){vTaskDelay(pdMS_TO_TICKS(10));continue;}
    auto result=afe->fetch_with_delay(data,pdMS_TO_TICKS(100));
    if(!result||result->ret_value!=ESP_OK)continue;
    const size_t pos=processed_count.load(),take=std::min<size_t>(result->data_size/2,Samples-pos);
    memcpy(processed+pos,result->data,take*sizeof(int16_t));processed_count=pos+take;
    if(processed_count==Samples)fetching_done=true;
  }
}
void output(const char *kind,const int16_t *pcm,size_t count) {
  unsigned seq=0;
  for(size_t pos=0;pos<count;pos+=160){
    const size_t n=std::min<size_t>(160,count-pos);unsigned char encoded[429]{};size_t written=0;
    if(mbedtls_base64_encode(encoded,sizeof(encoded),&written,reinterpret_cast<const unsigned char *>(pcm+pos),n*2))break;
    printf("CAP kind=%s seq=%u samples=%u data=%s\n",kind,seq++,unsigned(n),encoded);
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}
}
extern "C" void app_main() {
  usb_serial_jtag_driver_config_t usb{};usb.tx_buffer_size=4096;usb.rx_buffer_size=256;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));usb_serial_jtag_vfs_use_driver();
  ESP_ERROR_CHECK(nvs_flash_init());ESP_ERROR_CHECK(board::audio_init());board::capture_enabled(false);board::silence();
  auto cfg=afe_config_init("MR",nullptr,AFE_TYPE_FD,AFE_MODE_LOW_COST);
  cfg->wakenet_init=false;cfg->vad_model_name=nullptr;cfg->vad_init=true;
  cfg->aec_init=true;cfg->aec_mode=AEC_MODE_FD_LOW_COST;cfg->vad_mute_playback=false;
  cfg->ns_init=false;cfg->afe_ns_mode=AFE_NS_MODE_WEBRTC;cfg->memory_alloc_mode=AFE_MEMORY_ALLOC_MORE_PSRAM;
  cfg->afe_perferred_core=0;cfg->afe_perferred_priority=7;
  afe=esp_afe_handle_from_config(cfg);data=afe->create_from_config(cfg);afe_config_free(cfg);
  raw=static_cast<int16_t *>(heap_caps_calloc(Samples,2,MALLOC_CAP_SPIRAM));
  processed=static_cast<int16_t *>(heap_caps_calloc(Samples,2,MALLOC_CAP_SPIRAM));
  configASSERT(data&&raw&&processed);
  xTaskCreatePinnedToCore(feed,"diag-feed",8192,nullptr,8,nullptr,0);
  xTaskCreatePinnedToCore(fetch,"diag-fetch",8192,nullptr,6,nullptr,1);
  ESP_LOGI("capture_diag","READY microphone=off network=off amplifier=off; USB capture command required");
  char command[32]{};size_t used=0;
  while(true){
    uint8_t c;
    if(usb_serial_jtag_read_bytes(&c,1,pdMS_TO_TICKS(50))!=1)continue;
    if(c!='\n'&&c!='\r'){if(used<sizeof(command)-1)command[used++]=c;continue;}
    command[used]=0;used=0;if(strcmp(command,"capture"))continue;
    // One capture per boot avoids reusing AFE history or partially filled queues.
    board::capture_enabled(true);active=true;
    printf("CAP begin rate=16000 samples=64000 channels=raw,afe network=off\n");fflush(stdout);
    const auto start=esp_timer_get_time();
    while((!feeding_done||!fetching_done)&&esp_timer_get_time()-start<7000000)vTaskDelay(pdMS_TO_TICKS(10));
    board::capture_enabled(false);active=false;board::silence();vTaskDelay(pdMS_TO_TICKS(150));
    printf("CAP recording_finished microphone=off network=off; exporting bounded buffers\n");fflush(stdout);
    output("raw",raw,raw_count);output("afe",processed,processed_count);
    printf("CAP done raw=%u afe=%u microphone=off network=off amplifier=off\n",unsigned(raw_count),unsigned(processed_count));fflush(stdout);
    memset(raw,0,Samples*2);memset(processed,0,Samples*2);
    while(true)vTaskDelay(pdMS_TO_TICKS(1000));
  }
}
