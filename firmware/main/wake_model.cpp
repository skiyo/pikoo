#include "wake_model.hpp"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "mbedtls/base64.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/schema/schema_generated.h"
extern "C" {
#include "tensorflow/lite/experimental/microfrontend/lib/frontend.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend_util.h"
}
#include <algorithm>
#include <cmath>
#include <cstring>
#include <atomic>
static std::atomic<uint32_t> inference_max{0}, inference_count{0};
static std::atomic<float> latest_score{0}, interval_peak{0}, raw_interval_peak{0};
static std::atomic<uint32_t> detection_count{0}, error_count{0};
static std::atomic<bool> trace_requested{false};
static std::atomic<bool> capture_requested{false};
static std::atomic<bool> diagnostics_cancelled{false};
static unsigned trace_remaining=0,trace_sequence=0;
static size_t capture_remaining=0;
static unsigned capture_sequence=0;
void wake_trace_start(){trace_requested=true;}
void wake_capture_start(){capture_requested=true;}
void wake_cancel_diagnostics(){trace_requested=false;capture_requested=false;diagnostics_cancelled=true;}
static void peak(std::atomic<float> &target,float value) {
  auto before=target.load();
  while(before<value&&!target.compare_exchange_weak(before,value)){}
}
float wake_score(){return latest_score.load();}
float wake_peak_score(){return interval_peak.exchange(0);}
float wake_raw_peak_score(){return raw_interval_peak.exchange(0);}
uint32_t wake_detection_count(){return detection_count.load();}
uint32_t wake_error_count(){return error_count.load();}
uint32_t wake_max_inference_us(){return inference_max.load();}
uint32_t wake_inference_count(){return inference_count.load();}
extern const unsigned char
    model_start[] asm("_binary_nihao_pikoo_tflite_start");
static FrontendState frontend{};
static tflite::MicroInterpreter *interpreter;
static tflite::MicroMutableOpResolver<18> resolver;
static int slices = 0, prob_count = 0;
static float probabilities[5]{};
bool wake_init() {
  FrontendConfig cfg{};
  FrontendFillConfigWithDefaults(&cfg);
  cfg.window.size_ms = 30;
  cfg.window.step_size_ms = 10;
  cfg.filterbank.num_channels = 40;
  cfg.filterbank.lower_band_limit = 125;
  cfg.filterbank.upper_band_limit = 7500;
  cfg.noise_reduction.smoothing_bits = 10;
  cfg.noise_reduction.even_smoothing = .025;
  cfg.noise_reduction.odd_smoothing = .06;
  cfg.noise_reduction.min_signal_remaining = .05;
  cfg.pcan_gain_control.enable_pcan = 1;
  cfg.pcan_gain_control.strength = .95;
  cfg.pcan_gain_control.offset = 80;
  cfg.pcan_gain_control.gain_bits = 21;
  cfg.log_scale.enable_log = 1;
  cfg.log_scale.scale_shift = 6;
  if (!FrontendPopulateState(&cfg, &frontend, 16000))
    return false;
  resolver.AddCallOnce();
  resolver.AddVarHandle();
  resolver.AddReadVariable();
  resolver.AddAssignVariable();
  resolver.AddStridedSlice();
  resolver.AddConcatenation();
  resolver.AddConv2D();
  resolver.AddDepthwiseConv2D();
  resolver.AddReshape();
  resolver.AddFullyConnected();
  resolver.AddLogistic();
  resolver.AddAveragePool2D();
  resolver.AddQuantize();
  resolver.AddDequantize();
  resolver.AddMul();
  resolver.AddAdd();
  resolver.AddMean();
  resolver.AddExpandDims();
  auto arena = static_cast<uint8_t *>(
      heap_caps_aligned_alloc(16, 262144, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!arena)
    return false;
  auto allocator = tflite::MicroAllocator::Create(arena, 262144);
  auto variables = tflite::MicroResourceVariables::Create(allocator, 24);
  interpreter = new tflite::MicroInterpreter(tflite::GetModel(model_start),
                                             resolver, allocator, variables);
  if (interpreter->AllocateTensors() != kTfLiteOk)
    return false;
  auto input = interpreter->input(0);
  if (input->type != kTfLiteInt8 || input->bytes != 120)
    return false;
  ESP_LOGI("wake", "experimental model ready; arena=%u",
           unsigned(interpreter->arena_used_bytes()));
  return true;
}
void wake_reset() {
  trace_remaining=0;capture_remaining=0;
  slices = prob_count = 0;
  std::fill_n(probabilities, 5, 0);
  FrontendReset(&frontend);
  latest_score=0;
  if (interpreter)
    interpreter->Reset();
}
bool wake_feed(const int16_t *pcm, size_t count) {
  if (!interpreter) {
    return false;
  }
  if(diagnostics_cancelled.exchange(false))wake_reset();
  if(trace_requested.exchange(false)){
    wake_reset();trace_remaining=200;trace_sequence=0;
  }
  if(capture_requested.exchange(false)){
    wake_reset();
    capture_remaining=64000;capture_sequence=0;
    ESP_LOGI("wake_pcm","begin rate=16000 samples=64000");
  }
  const bool local_diagnostic=trace_remaining||capture_remaining;
  // Four-second opt-in USB diagnostic, confined to standby by the caller.
  // Raw audio is private; it is never forwarded to the voice server here.
  for(size_t pos=0;capture_remaining&&pos<count;){
    size_t n=std::min<size_t>(160,std::min(capture_remaining,count-pos)),written=0;
    unsigned char encoded[429]{};
    if(mbedtls_base64_encode(encoded,sizeof(encoded),&written,reinterpret_cast<const unsigned char *>(pcm+pos),n*2)!=0)break;
    ESP_LOGI("wake_pcm","seq=%u count=%u data=%s",capture_sequence++,unsigned(n),encoded);
    capture_remaining-=n;pos+=n;
    if(!capture_remaining)ESP_LOGI("wake_pcm","done");
  }
  bool detected = false;
  while (count) {
    size_t used = 0;
    auto f = FrontendProcessSamples(&frontend, pcm, count, &used);
    if (!used)
      break;
    pcm += used;
    count -= used;
    if (f.size != 40)
      continue;
    auto input = interpreter->input(0);
    for (int i = 0; i < 40; ++i) {
      float value = f.values[i] * .0390625f;
      int quant =
          std::lround(value / input->params.scale) + input->params.zero_point;
      input->data.int8[slices * 40 + i] = std::clamp(quant, -128, 127);
    }
    if (++slices < 3) {
      continue;
    }
    slices = 0;
    char trace_hex[241]{};
    if(trace_remaining){
      const char digits[]="0123456789abcdef";
      for(int j=0;j<120;j++){auto v=uint8_t(input->data.int8[j]);trace_hex[2*j]=digits[v>>4];trace_hex[2*j+1]=digits[v&15];}
    }
    auto started=esp_timer_get_time();
    auto result=interpreter->Invoke();
    auto elapsed=static_cast<uint32_t>(esp_timer_get_time()-started);
    inference_max=std::max(inference_max.load(),elapsed);
    ++inference_count;
    if (result != kTfLiteOk) {
      ++error_count;
      if(trace_remaining)--trace_remaining;
      continue;
    }
    auto out = interpreter->output(0);
    float p = ((out->type == kTfLiteUInt8 ? int(out->data.uint8[0])
                                          : int(out->data.int8[0])) -
               out->params.zero_point) *
              out->params.scale;
    // Explicit USB-only diagnostic: bounded quantized features, never PCM.
    // Treat traces as private data; no trace is produced during normal use.
    if(trace_remaining){
      ESP_LOGI("wake_trace","seq=%u features=%s p=%.6f",trace_sequence++,trace_hex,double(p));
      --trace_remaining;
    }
    probabilities[prob_count++ % 5] = p;
    peak(raw_interval_peak,p);
    if (prob_count >= 5) {
      float sum = 0;
      for (float v : probabilities)
        sum += v;
      latest_score=sum/5;
      peak(interval_peak,sum/5);
      detected |= (sum / 5 >= .90f);
    }
  }
  // An explicit private diagnostic must never open a cloud voice session.
  // Discard its recurrent history before normal detection resumes as well.
  if(local_diagnostic){
    if(!trace_remaining&&!capture_remaining)wake_reset();
    return false;
  }
  if(detected)++detection_count;
  return detected;
}
