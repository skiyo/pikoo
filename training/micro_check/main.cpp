// Host execution of the pinned TFLM runtime. Timing and allocation are HOST
// measurements and must not be represented as ESP32-S3 measurements.
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
#include <array>
#include <string>

int main(int argc, char **argv) {
  const bool trace_mode=argc==5&&std::string(argv[3])=="--trace-output";
  if (argc != 2 && argc != 3 && !trace_mode) return 2;
  std::ifstream file(argv[1], std::ios::binary);
  std::vector<char> bytes((std::istreambuf_iterator<char>(file)), {});
  flatbuffers::Verifier verifier(reinterpret_cast<const uint8_t *>(bytes.data()), bytes.size());
  if (bytes.empty() || !tflite::VerifyModelBuffer(verifier)) return 3;
  tflite::MicroMutableOpResolver<19> resolver;
  resolver.AddCallOnce(); resolver.AddVarHandle(); resolver.AddReadVariable();
  resolver.AddAssignVariable(); resolver.AddStridedSlice(); resolver.AddConcatenation();
  resolver.AddConv2D(); resolver.AddDepthwiseConv2D(); resolver.AddReshape();
  resolver.AddFullyConnected(); resolver.AddLogistic(); resolver.AddAveragePool2D();
  resolver.AddQuantize(); resolver.AddDequantize(); resolver.AddMul(); resolver.AddAdd();
  resolver.AddMean(); resolver.AddExpandDims(); resolver.AddSoftmax();
  alignas(16) static uint8_t arena[262144];
  auto allocator = tflite::MicroAllocator::Create(arena, sizeof(arena));
  auto variables = tflite::MicroResourceVariables::Create(allocator, 24);
  tflite::MicroInterpreter interpreter(tflite::GetModel(bytes.data()), resolver, allocator, variables);
  if (interpreter.AllocateTensors() != kTfLiteOk) return 4;
  auto input = interpreter.input(0);
  if (input->type != kTfLiteInt8 || input->bytes != 120) return 5;
  if (argc >= 3) {
    std::ifstream fixture(argv[2], std::ios::binary);
    std::vector<char> features((std::istreambuf_iterator<char>(fixture)), {});
    if (features.empty() || features.size()%120) return 8;
    auto output=interpreter.output(0);
    if(output->type!=kTfLiteUInt8&&output->type!=kTfLiteInt8)return 9;
    if(!output->bytes||output->bytes>256)return 9;
    std::ofstream trace;
    if(trace_mode){trace.open(argv[4],std::ios::binary);if(!trace)return 10;}
    std::array<float,3> peaks{};
    for (int round=0;round<3;++round) {
      if (interpreter.Reset()!=kTfLiteOk) return 6;
      std::array<float,5> scores{};size_t count=0;
      for (size_t offset=0;offset<features.size();offset+=120) {
        std::copy_n(features.data()+offset,120,input->data.int8);
        if (interpreter.Invoke()!=kTfLiteOk) return 7;
        auto out=interpreter.output(0);
        if(trace_mode){trace.write(reinterpret_cast<const char *>(out->data.raw),out->bytes);if(!trace)return 10;}
        int raw=out->type==kTfLiteUInt8?int(out->data.uint8[0]):int(out->data.int8[0]);
        scores[count++%5]=(raw-out->params.zero_point)*out->params.scale;
        if(count>=5) {float sum=0;for(float score:scores)sum+=score;peaks[round]=std::max(peaks[round],sum/5);}
      }
    }
    if(trace_mode){
      std::cout << "{\"host_arena_used_bytes\":" << interpreter.arena_used_bytes()
                << ",\"trace_rounds\":3,\"trace_frames\":" << features.size()/120
                << ",\"trace_channels\":" << output->bytes
                << ",\"esp32_hardware_verified\":false}\n";
      return 0;
    }
    std::cout << "{\"host_arena_used_bytes\":" << interpreter.arena_used_bytes()
              << ",\"peaks\":[" << peaks[0] << "," << peaks[1] << "," << peaks[2] << "]}\n";
    return 0;
  }
  for (int round = 0; round < 3; ++round) {
    if (interpreter.Reset() != kTfLiteOk) return 6;
    for (int n = 0; n < 100; ++n) {
      // Exercise low/high/zero features, variable state, and explicit resets.
      std::fill_n(input->data.int8, input->bytes, int8_t(round==0 ? -128 : round==1 ? 127 : input->params.zero_point));
      if (interpreter.Invoke() != kTfLiteOk) return 7;
    }
  }
  std::cout << "{\"status\":\"host-tflm-passed\",\"invocations\":300,\"resets\":3,"
            << "\"host_arena_used_bytes\":" << interpreter.arena_used_bytes()
            << ",\"arena_budget_bytes\":262144,\"esp32_hardware_verified\":false}\n";
}
