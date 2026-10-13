cmake_minimum_required(VERSION 3.20)
project(pikoo_micro_check LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(TFLM_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../firmware/managed_components/espressif__esp-tflite-micro" CACHE PATH "Pinned ESP-IDF TFLM component")
if(NOT EXISTS "${TFLM_ROOT}/tensorflow/lite/micro/micro_interpreter.cc")
  message(FATAL_ERROR "Run the ESP-IDF configure/build first to obtain pinned managed components")
endif()
set(LITE "${TFLM_ROOT}/tensorflow/lite")
file(GLOB MICRO "${LITE}/micro/*.cc" "${LITE}/micro/kernels/*.cc"
  "${LITE}/micro/tflite_bridge/*.cc" "${LITE}/micro/memory_planner/*.cc"
  "${LITE}/micro/arena_allocator/*.cc")
list(FILTER MICRO EXCLUDE REGEX "(_test|_benchmark|test_helpers|mock_micro_graph)\\.cc$")
add_library(tflm STATIC ${MICRO}
  "${LITE}/kernels/kernel_util.cc" "${LITE}/core/c/common.cc"
  "${LITE}/core/api/flatbuffer_conversions.cc" "${LITE}/core/api/tensor_utils.cc"
  "${LITE}/kernels/internal/common.cc" "${LITE}/kernels/internal/quantization_util.cc"
  "${LITE}/kernels/internal/portable_tensor_utils.cc" "${LITE}/kernels/internal/tensor_utils.cc"
  "${LITE}/kernels/internal/tensor_ctypes.cc" "${LITE}/kernels/internal/reference/portable_tensor_utils.cc"
  "${TFLM_ROOT}/tensorflow/compiler/mlir/lite/core/api/error_reporter.cc"
  "${TFLM_ROOT}/tensorflow/compiler/mlir/lite/schema/schema_utils.cc")
target_include_directories(tflm PUBLIC "${TFLM_ROOT}" "${TFLM_ROOT}/third_party/gemmlowp"
  "${TFLM_ROOT}/third_party/flatbuffers/include" "${TFLM_ROOT}/third_party/ruy")
target_compile_definitions(tflm PUBLIC TF_LITE_STATIC_MEMORY TF_LITE_DISABLE_X86_NEON)
target_compile_options(tflm PRIVATE -O2 -Wno-deprecated-declarations)
add_executable(pikoo_micro_check main.cpp)
target_link_libraries(pikoo_micro_check PRIVATE tflm)
