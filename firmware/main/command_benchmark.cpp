// Offline corpus replay only: private cases are embedded or sent over USB.
// No microphone, speaker initialization, Wi-Fi, credentials or cloud access.
#include "board.hpp"
#include "pikoo_phonetic.hpp"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
extern "C" {
#include "esp_mn_models.h"
#include "esp_mn_speech_commands.h"
#include "model_path.h"
}
#include <algorithm>
#include <cassert>
#include <cinttypes>
#include <cstring>
#include <cstdio>
#include "mbedtls/base64.h"

extern const unsigned char models_start[] asm("_binary_command_models_bin_start");
extern const unsigned char cases_start[] asm("_binary_command_cases_bin_start");
extern const unsigned char cases_end[] asm("_binary_command_cases_bin_end");
namespace {
uint32_t read32(const unsigned char *&p) {
  assert(p+4<=cases_end);uint32_t value;std::memcpy(&value,p,4);p+=4;return value;
}
void graphics(void *) {
  pikoo::eyes::Animator animator;
  while(true) {
    pikoo::eyes::Input input{};input.state=pikoo::eyes::State::Idle;
    input.time_ms=esp_timer_get_time()/1000;
    board::display_frame(animator.update(input),"LOCAL CHECK");
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}
}
extern "C" void app_main() {
  heap_caps_malloc_extmem_enable(512);
  gpio_config_t gpio{};gpio.pin_bit_mask=1ULL<<board::Amp;gpio.mode=GPIO_MODE_OUTPUT;
  ESP_ERROR_CHECK(gpio_config(&gpio));gpio_set_level(board::Amp,0);
  usb_serial_jtag_driver_config_t usb{};usb.tx_buffer_size=8192;usb.rx_buffer_size=4096;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));usb_serial_jtag_vfs_use_driver();
  ESP_ERROR_CHECK(board::display_init());
  xTaskCreatePinnedToCore(graphics,"command-eyes",8192,nullptr,2,nullptr,1);
  auto models=srmodel_load(models_start);assert(models&&models->num>=2);
  // MultiNet6/7 need the FST command dictionary in addition to acoustic weights.
  // Without it, the upstream loader falls back to a filesystem base path.
  assert(esp_srmodel_filter(models,"fst",nullptr));
  auto name=esp_srmodel_filter(models,ESP_MN_PREFIX,ESP_MN_CHINESE);assert(name);
  auto mn=esp_mn_handle_from_name(name);assert(mn);
  auto data=mn->create(name,10000);assert(data);
  if(mn->switch_loader_mode)data=mn->switch_loader_mode(data,ESP_MN_LOAD_FROM_PSRAM);
  assert(data);
  ESP_ERROR_CHECK(esp_mn_commands_alloc(mn,data));
  const auto &commands=pikoo::PhoneticCommands;
  for(unsigned i=0;i<commands.size();++i)
    ESP_ERROR_CHECK(esp_mn_commands_add(i+1,commands[i]));
  auto errors=esp_mn_commands_update();assert(!errors||errors->num==0);
  // TRAIN-only diagnostic: expose low-confidence completed commands as well.
  // The reported confirmation criterion below remains 0.7 in this probe.
  mn->set_det_threshold(data,.1f);
  int chunk=mn->get_samp_chunksize(data);assert(chunk>0&&chunk<=2048);
  auto buffer=static_cast<int16_t *>(heap_caps_calloc(chunk,sizeof(int16_t),MALLOC_CAP_SPIRAM));assert(buffer);
  ESP_LOGI("command_bench","model=%s chunk=%d internal=%u psram=%u microphone=off amplifier=off network=off",
    name,chunk,unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
  auto cursor=cases_start;assert(read32(cursor)==0x504b4342);auto count=read32(cursor);
  assert(count<=2048);
  // A zero-case private image accepts bounded PCM frames over owned USB.
  // This diagnostic never records the microphone or connects to the network.
  if(count==0) {
    auto line=static_cast<char *>(heap_caps_calloc(1500,1,MALLOC_CAP_SPIRAM));assert(line);
    auto replay=static_cast<int16_t *>(heap_caps_calloc(160000,sizeof(int16_t),MALLOC_CAP_SPIRAM));assert(replay);
    unsigned length=0,id=0,label=0,expected=0,received=0,sequence=0;
    uint32_t checksum=2166136261u;bool active=false;
    float peak=0,top=0;int top_id=0;
    auto reply=[](const char *kind,unsigned value){
      std::printf("PROBE {\"kind\":\"%s\",\"value\":%u}\n",kind,value);std::fflush(stdout);
    };
    reply("ready",unsigned(chunk));
    while(true) {
      uint8_t byte;
      if(usb_serial_jtag_read_bytes(&byte,1,pdMS_TO_TICKS(100))!=1)continue;
      if(byte=='\r')continue;
      if(byte!='\n') {
        if(length+1<1500)line[length++]=char(byte);
        else {length=0;active=false;reply("error",1);}
        continue;
      }
      line[length]=0;length=0;
      if(!line[0])continue;
      if(!std::strcmp(line,"R")){active=false;reply("ready",unsigned(chunk));continue;}
      if(line[0]=='B') {
        unsigned requested_id,requested_label,requested_samples;char extra;
        if(std::sscanf(line,"B %u %u %u %c",&requested_id,&requested_label,&requested_samples,&extra)!=3 ||
           requested_label>1||requested_samples==0||requested_samples>160000) {
          active=false;reply("error",2);continue;
        }
        id=requested_id;label=requested_label;expected=requested_samples;
        received=sequence=0;checksum=2166136261u;peak=top=0;top_id=0;
        mn->clean(data);active=true;reply("begin",id);continue;
      }
      if(line[0]=='F'&&active) {
        unsigned seq;int offset=0;
        if(std::sscanf(line,"F %u %n",&seq,&offset)!=1||offset<=0||seq!=sequence) {
          active=false;reply("error",3);continue;
        }
        size_t bytes=0;auto maximum_samples=std::min<unsigned>(chunk,expected-received);
        if(!maximum_samples||mbedtls_base64_decode(reinterpret_cast<unsigned char *>(buffer),chunk*2,&bytes,
           reinterpret_cast<const unsigned char *>(line+offset),std::strlen(line+offset)) || !bytes || bytes%2 || bytes>maximum_samples*2) {
          active=false;reply("error",4);continue;
        }
        auto needed=unsigned(bytes/2);
        for(size_t j=0;j<bytes;++j){checksum^=reinterpret_cast<uint8_t *>(buffer)[j];checksum*=16777619u;}
        std::copy_n(buffer,needed,replay+received);
        received+=needed;reply("frame",sequence++);
        if(sequence%8==0)vTaskDelay(1);
        continue;
      }
      if(line[0]=='E'&&active) {
        unsigned check;char extra;
        if(std::sscanf(line,"E %u %c",&check,&extra)!=1||received!=expected||check!=checksum) {
          active=false;reply("error",5);continue;
        }
        auto process_started=esp_timer_get_time();
        // Finish the bounded transfer before running inference. This isolates
        // USB backpressure from recognition and retains exactly the same PCM.
        for(unsigned pos=0;pos<received;pos+=chunk) {
          auto take=std::min<unsigned>(chunk,received-pos);
          std::copy_n(replay+pos,take,buffer);std::fill(buffer+take,buffer+chunk,0);
          if(mn->detect(data,buffer)==ESP_MN_STATE_DETECTED) {
            auto result=mn->get_results(data);
            if(result&&result->num) {
              if(result->prob[0]>top){top=result->prob[0];top_id=result->command_id[0];}
              if(result->command_id[0]==1)peak=std::max(peak,result->prob[0]);
            }
          }
          if((pos/chunk)%8==0)vTaskDelay(1);
        }
        active=false;
        std::printf("PROBE {\"kind\":\"result\",\"id\":%u,\"label\":%u,\"samples\":%u,\"checksum\":%u,"
          "\"top_id\":%d,\"top_probability\":%.6f,\"target_score\":%.6f,\"process_us\":%lld,\"internal_free_bytes\":%u,\"psram_free_bytes\":%u}\n",
          id,label,received,unsigned(checksum),top_id,double(top),double(peak),
          static_cast<long long>(esp_timer_get_time()-process_started),unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));std::fflush(stdout);continue;
      }
      active=false;reply("error",6);
    }
  }
  unsigned targets=0,hits=0,negatives=0,false_wakes=0,frames=0;
  uint32_t maximum=0;uint64_t total=0;
  for(unsigned n=0;n<count;++n) {
    auto id=read32(cursor),label=read32(cursor),samples=read32(cursor);
    assert(label<=1&&samples>0&&samples<=160000&&cursor+samples*2<=cases_end);
    auto pcm=reinterpret_cast<const int16_t *>(cursor);cursor+=samples*2;
    mn->clean(data);float target_peak=0,top_probability=0;int top_id=0;
    for(unsigned pos=0;pos<samples;pos+=chunk) {
      auto length=std::min<unsigned>(chunk,samples-pos);
      std::copy_n(pcm+pos,length,buffer);std::fill(buffer+length,buffer+chunk,0);
      auto started=esp_timer_get_time();auto state=mn->detect(data,buffer);
      auto elapsed=uint32_t(esp_timer_get_time()-started);maximum=std::max(maximum,elapsed);total+=elapsed;++frames;
      if(state==ESP_MN_STATE_DETECTED) {
        auto result=mn->get_results(data);
        if(result&&result->num) {
          if(result->prob[0]>top_probability){top_probability=result->prob[0];top_id=result->command_id[0];}
          if(result->command_id[0]==1)target_peak=std::max(target_peak,result->prob[0]);
        }
      }
      if(frames%8==0)vTaskDelay(1);
    }
    // Confirm only the best complete command over the fixed replay window.
    bool detected=top_id==1&&top_probability>=.7f;
    if(label){++targets;if(detected)++hits;}else{++negatives;if(detected)++false_wakes;}
    ESP_LOGI("command_case","{\"id\":%u,\"label\":%u,\"detected\":%s,\"target_score\":%.6f,\"top_id\":%d,\"top_probability\":%.6f}",
      id,label,detected?"true":"false",double(target_peak),top_id,double(top_probability));
  }
  assert(cursor==cases_end);
  while(true) {
    ESP_LOGI("command_bench","{\"status\":\"synthetic-command-probe\",\"cases\":%u,\"targets\":%u,\"hits\":%u,\"negatives\":%u,\"false_wakes\":%u,\"frames\":%u,\"mean_frame_us\":%" PRIu64 ",\"max_frame_us\":%lu,\"internal_free_bytes\":%u,\"psram_free_bytes\":%u,\"microphone_enabled\":false,\"network_enabled\":false,\"amplifier_enabled\":false}",
      count,targets,hits,negatives,false_wakes,frames,total/std::max(1u,frames),(unsigned long)maximum,
      unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
    vTaskDelay(pdMS_TO_TICKS(5000));
  }
}
