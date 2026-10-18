// Synthetic-only development image. No microphone/audio initialization,
// Wi-Fi, credentials, household recordings or cloud sessions are used.
#include "board.hpp"
#include "wake_model.hpp"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include <algorithm>
#include <atomic>
#include <cinttypes>

namespace {
std::atomic<bool> finished{false};
void graphics(void *) {
  pikoo::eyes::Animator animator;
  while (true) {
    auto started=esp_timer_get_time();
    pikoo::eyes::Input input{};
    input.state=pikoo::eyes::State::Idle;
    input.time_ms=started/1000;
    board::display_frame(animator.update(input),finished?"BENCH DONE":"BENCHMARK");
    auto elapsed=(esp_timer_get_time()-started)/1000;
    vTaskDelay(pdMS_TO_TICKS(elapsed<50?50-elapsed:1));
  }
}

void benchmark(void *) {
  if (!wake_init()) {
    ESP_LOGE("wake_bench","allocation_failed microphone=off network=off amplifier=off");
    vTaskDelete(nullptr);
    return;
  }
  constexpr unsigned count=600;
  uint32_t durations[count]{};
  int16_t pcm[480]{};
  uint32_t random=20261018;
  TickType_t deadline=xTaskGetTickCount();
  unsigned overruns=0;
  uint64_t sum=0;
  wake_reset();
  for (unsigned n=0;n<count+20;++n) {
    for (auto &sample:pcm) {
      random^=random<<13;random^=random>>17;random^=random<<5;
      sample=int16_t(int(random&4095)-2048);
    }
    auto started=esp_timer_get_time();
    wake_feed(pcm,480);
    auto elapsed=uint32_t(esp_timer_get_time()-started);
    if (n>=20) {
      durations[n-20]=elapsed;sum+=elapsed;
      if (elapsed>30000) ++overruns;
    }
    if (elapsed>=30000) {
      // An over-budget candidate must report its failure instead of starving
      // idle/graphics until the watchdog resets the diagnostic image.
      deadline=xTaskGetTickCount();
      vTaskDelay(pdMS_TO_TICKS(1));
    } else vTaskDelayUntil(&deadline,pdMS_TO_TICKS(30));
    if (n%100==0) ESP_LOGI("wake_bench","progress=%u microphone=off network=off",n);
  }
  std::sort(durations,durations+count);
  finished=true;
  // Repeat the result so a monitor opened after flashing cannot miss it.
  while (true) {
    ESP_LOGI("wake_bench",
      "{\"status\":\"synthetic-device-timing\",\"model_bytes\":%u,"
      "\"iterations\":%u,\"frontend_plus_inference_mean_us\":%" PRIu64 ","
      "\"frontend_plus_inference_p99_us\":%lu,\"frontend_plus_inference_max_us\":%lu,"
      "\"inference_max_us\":%lu,\"deadline_misses\":%u,\"wake_errors\":%lu,"
      "\"internal_free_bytes\":%u,\"psram_free_bytes\":%u,\"display_fps\":%.1f,"
      "\"microphone_enabled\":false,\"network_enabled\":false,"
      "\"amplifier_enabled\":false,\"live_audio_concurrency_validated\":false}",
      unsigned(PIKOO_BENCH_MODEL_BYTES),count,sum/count,
      (unsigned long)durations[(count*99+99)/100-1],(unsigned long)durations[count-1],
      (unsigned long)wake_max_inference_us(),overruns,(unsigned long)wake_error_count(),
      unsigned(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
      unsigned(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),board::display_fps());
    vTaskDelay(pdMS_TO_TICKS(5000));
  }
}
}

extern "C" void app_main() {
  heap_caps_malloc_extmem_enable(512);
  usb_serial_jtag_driver_config_t usb{};
  usb.tx_buffer_size=4096;usb.rx_buffer_size=256;
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
  usb_serial_jtag_vfs_use_driver();
  ESP_LOGI("wake_bench","starting synthetic-only diagnostic image");
  gpio_config_t config{};
  config.pin_bit_mask=1ULL<<board::Amp;
  config.mode=GPIO_MODE_OUTPUT;
  ESP_ERROR_CHECK(gpio_config(&config));
  gpio_set_level(board::Amp,0);
  ESP_ERROR_CHECK(board::display_init());
  xTaskCreatePinnedToCore(graphics,"bench-eyes",8192,nullptr,2,nullptr,1);
  xTaskCreatePinnedToCore(benchmark,"wake-bench",12288,nullptr,6,nullptr,1);
}
