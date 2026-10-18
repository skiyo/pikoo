// Optional experimental local verifier. No microphone logging, network or NVS.
#include "wake_verifier.hpp"
#include "wake_model.hpp"
#include "pikoo_phonetic.hpp"
#include "pikoo_wake_replay.hpp"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
extern "C" {
#include "esp_mn_models.h"
#include "esp_mn_speech_commands.h"
#include "model_path.h"
}
#include <atomic>
#include <new>

#ifndef PIKOO_WAKE_VETO_CUTOFF
#define PIKOO_WAKE_VETO_CUTOFF .5f
#endif
extern const unsigned char veto_models[] asm("_binary_wake_veto_models_bin_start");
namespace {
using Replay=pikoo::WakeReplay;
enum Phase {Idle,Collecting,Running,Done};
std::atomic<Phase> phase{Idle};
std::atomic<uint32_t> generation{0},candidates{0},rejections{0},cancelled{0},errors{0},last_us{0};
uint32_t observed_generation=0,observed_epoch=UINT32_MAX,job_generation=0;
uint64_t rearm_at=0;
TaskHandle_t worker_handle=nullptr;
const esp_mn_iface_t *mn=nullptr;
model_iface_data_t *model=nullptr;
Replay *replay=nullptr;
int16_t *waveform=nullptr;
pikoo::PhoneticDecision decision;
bool job_cancelled=false,job_failed=false,initialized=false;
void worker(void *) {
  while(true){
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    if(phase.load(std::memory_order_acquire)!=Running)continue;
    auto started=esp_timer_get_time();mn->clean(model);
    decision={};job_cancelled=job_failed=false;
    for(size_t pos=0;pos<Replay::Samples;pos+=512){
      if(generation.load()!=job_generation){job_cancelled=true;break;}
      // The declared replay is not a multiple of 512. Never read beyond it.
      int16_t tail[512]{};auto count=std::min<size_t>(512,Replay::Samples-pos);
      auto pcm=waveform+pos;
      if(count!=512){std::copy_n(pcm,count,tail);pcm=tail;}
      if(mn->detect(model,pcm)==ESP_MN_STATE_DETECTED){
        auto result=mn->get_results(model);
        if(result&&result->num&&!decision.observe(result->command_id[0],result->prob[0])){
          job_failed=true;break;
        }
      }
      if((pos/512)%8==0)vTaskDelay(1);
    }
    last_us=uint32_t(esp_timer_get_time()-started);
    phase.store(Done,std::memory_order_release);
  }
}
}
bool wake_verifier_init(){
  auto list=srmodel_load(veto_models);
  if(!list||!esp_srmodel_filter(list,"fst",nullptr))return false;
  auto name=esp_srmodel_filter(list,ESP_MN_PREFIX,ESP_MN_CHINESE);
  if(!name||(mn=esp_mn_handle_from_name(name))==nullptr)return false;
  model=mn->create(name,10000);if(!model)return false;
  if(mn->switch_loader_mode)model=mn->switch_loader_mode(model,ESP_MN_LOAD_FROM_PSRAM);
  if(!model||mn->get_samp_chunksize(model)!=512||esp_mn_commands_alloc(mn,model)!=ESP_OK)return false;
  const auto &commands=pikoo::PhoneticCommands;
  for(unsigned i=0;i<commands.size();++i)if(esp_mn_commands_add(i+1,commands[i])!=ESP_OK)return false;
  auto bad=esp_mn_commands_update();if(bad&&bad->num)return false;
  mn->set_det_threshold(model,.1f);
  auto history=static_cast<int16_t *>(heap_caps_calloc(Replay::History,sizeof(int16_t),MALLOC_CAP_SPIRAM));
  waveform=static_cast<int16_t *>(heap_caps_calloc(Replay::Samples,sizeof(int16_t),MALLOC_CAP_SPIRAM));
  if(!history||!waveform)return false;
  replay=new(std::nothrow) Replay(history,waveform);if(!replay)return false;
  if(xTaskCreatePinnedToCore(worker,"wake-confirm",8192,nullptr,3,&worker_handle,0)!=pdPASS)return false;
  initialized=true;
  ESP_LOGI("wake_veto","experimental veto ready; microphone acceptance pending; internal=%u psram=%u",
    unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
  return true;
}
void wake_verifier_invalidate(){++generation;}
void wake_verifier_reset(){
  wake_verifier_invalidate();
  observed_generation=generation.load();observed_epoch=UINT32_MAX;
  if(replay)replay->reset();
  if(phase.load(std::memory_order_acquire)!=Running)phase=Idle;
  wake_reset();
}
bool wake_verifier_feed(const int16_t *pcm,size_t count,uint32_t epoch){
  if(!initialized)return false; // No silent bypass when verifier initialization fails.
  auto current=generation.load();
  if(observed_generation!=current||observed_epoch!=epoch){
    observed_generation=current;observed_epoch=epoch;replay->reset();wake_reset();
    if(phase.load(std::memory_order_acquire)!=Running)phase=Idle;
  }
  replay->append(pcm,count);
  auto state=phase.load(std::memory_order_acquire);
  if(state==Done){
    bool accepted=!job_cancelled&&!job_failed&&current==job_generation&&!decision.rejected(PIKOO_WAKE_VETO_CUTOFF);
    if(job_cancelled||current!=job_generation)++cancelled;
    else if(job_failed)++errors;
    else if(decision.rejected(PIKOO_WAKE_VETO_CUTOFF))++rejections;
    replay->release();phase=Idle;wake_reset();
    if(accepted&&generation.load()==job_generation)return true;
  }
  if(phase==Collecting&&replay->ready()){
    phase.store(Running,std::memory_order_release);xTaskNotifyGive(worker_handle);return false;
  }
  auto now=uint64_t(esp_timer_get_time()/1000);
  if(phase==Idle&&now>=rearm_at&&wake_feed(pcm,count,false)){
    ++candidates;job_generation=current;rearm_at=now+5000;
    replay->trigger();phase=Collecting;
  }
  return false;
}
uint32_t wake_verifier_candidates(){return candidates.load();}
uint32_t wake_verifier_rejected(){return rejections.load();}
uint32_t wake_verifier_cancelled(){return cancelled.load();}
uint32_t wake_verifier_errors(){return errors.load();}
uint32_t wake_verifier_last_us(){return last_us.load();}
