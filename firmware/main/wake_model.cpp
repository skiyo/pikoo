#include "wake_model.hpp"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
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
  slices = prob_count = 0;
  std::fill_n(probabilities, 5, 0);
  FrontendReset(&frontend);
  if (interpreter)
    interpreter->Reset();
}
bool wake_feed(const int16_t *pcm, size_t count) {
  if (!interpreter) {
    return false;
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
    auto started=esp_timer_get_time();
    auto result=interpreter->Invoke();
    auto elapsed=static_cast<uint32_t>(esp_timer_get_time()-started);
    inference_max=std::max(inference_max.load(),elapsed);
    ++inference_count;
    if (result != kTfLiteOk)
      continue;
    auto out = interpreter->output(0);
    float p = ((out->type == kTfLiteUInt8 ? int(out->data.uint8[0])
                                          : int(out->data.int8[0])) -
               out->params.zero_point) *
              out->params.scale;
    probabilities[prob_count++ % 5] = p;
    if (prob_count >= 5) {
      float sum = 0;
      for (float v : probabilities)
        sum += v;
      detected |= (sum / 5 >= .90f);
    }
  }
  return detected;
}
