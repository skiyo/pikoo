#include "board_audio.hpp"
#include "bsp/esp32_s3_touch_lcd_1_83.h"
#include "esp_codec_dev_defaults.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <algorithm>
#include <vector>
namespace board {
static i2s_chan_handle_t tx, rx;
static std::atomic<uint32_t> epoch{0};
static uint32_t primed = UINT32_MAX;
static const audio_codec_if_t *dac, *adc;
esp_err_t audio_init() {
  ESP_ERROR_CHECK(bsp_i2c_init());
  i2s_chan_config_t chan =
      I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  chan.dma_desc_num = 4;
  chan.dma_frame_num = 160;
  chan.auto_clear = true;
  ESP_ERROR_CHECK(i2s_new_channel(&chan, &tx, &rx));
  i2s_std_config_t cfg{};
  cfg.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000);
  // ES7210 4x16-bit TDM captured as two 32-bit I2S slots (64 BCLK/LRCK).
  // ES8311 uses the high 16 bits of each playback slot on the same clock.
  cfg.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT,
                                                     I2S_SLOT_MODE_STEREO);
  cfg.gpio_cfg.mclk = BSP_I2S_MCLK;
  cfg.gpio_cfg.bclk = BSP_I2S_SCLK;
  cfg.gpio_cfg.ws = BSP_I2S_LCLK;
  cfg.gpio_cfg.dout = BSP_I2S_DOUT;
  cfg.gpio_cfg.din = BSP_I2S_DSIN;
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx, &cfg));
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx, &cfg));
  ESP_ERROR_CHECK(i2s_channel_enable(tx));
  ESP_ERROR_CHECK(i2s_channel_enable(rx));
  audio_codec_i2c_cfg_t bus{};
  bus.port = BSP_I2C_NUM;
  bus.bus_handle = bsp_i2c_get_handle();
  bus.addr = ES8311_CODEC_DEFAULT_ADDR;
  auto dac_bus = audio_codec_new_i2c_ctrl(&bus);
  bus.addr = ES7210_CODEC_DEFAULT_ADDR;
  auto adc_bus = audio_codec_new_i2c_ctrl(&bus);
  es8311_codec_cfg_t dc{};
  dc.ctrl_if = dac_bus;
  dc.gpio_if = audio_codec_new_gpio();
  dc.codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC;
  dc.pa_pin = BSP_POWER_AMP_IO;
  dc.use_mclk = true;
  dc.hw_gain.pa_voltage = 5;
  dc.hw_gain.codec_dac_voltage = 3.3;
  dac = es8311_codec_new(&dc);
  es7210_codec_cfg_t ac{};
  ac.ctrl_if = adc_bus;
  ac.mic_selected = 0x0f;
  adc = es7210_codec_new(&ac);
  if (!dac || !adc)
    return ESP_FAIL;
  esp_codec_dev_sample_info_t format{};
  format.sample_rate = 16000;
  format.bits_per_sample = 16;
  format.channel = 4;
  if (adc->set_fs(adc, &format) != 0)
    return ESP_FAIL;
  format.channel = 2;
  if (dac->set_fs(dac, &format) != 0)
    return ESP_FAIL;
  if (adc->set_mic_channel_gain(adc, 3, 24) != 0 ||
      adc->set_mic_channel_gain(adc, 12, 0) != 0)
    return ESP_FAIL;
  if (dac->set_vol(dac, -18) != 0 || dac->enable(dac, true) != 0 ||
      adc->enable(adc, true) != 0)
    return ESP_FAIL;
  silence();
  return ESP_OK;
}
bool capture(int16_t *out, size_t frames) {
  std::vector<int32_t> raw(frames * 2);
  size_t received = 0;
  if (i2s_channel_read(rx, raw.data(), raw.size() * 4, &received, 200) !=
          ESP_OK ||
      received != raw.size() * 4)
    return false;
  for (size_t i = 0; i < frames; ++i) {
    out[i * 4] = raw[i * 2] >> 16;
    out[i * 4 + 1] = raw[i * 2] & 0xffff;
    out[i * 4 + 2] = raw[i * 2 + 1] >> 16;
    out[i * 4 + 3] = raw[i * 2 + 1] & 0xffff;
  }
  return true;
}
void silence() {
  epoch.fetch_add(1);
  gpio_set_level(BSP_POWER_AMP_IO, 0);
}
uint32_t generation() { return epoch.load(); }
void drain() {
  vTaskDelay(pdMS_TO_TICKS(50));
} // DMA bound 4 x 10ms, plus scheduler margin.
bool play(const int16_t *mono, size_t samples, uint32_t expected) {
  if (expected != generation())
    return false;
  if (primed != expected) {
    // Flush every DMA descriptor while amplifier is off, before a new epoch.
    std::vector<int32_t> zero(1280, 0);
    size_t sent = 0;
    if (i2s_channel_write(tx, zero.data(), zero.size() * 4, &sent, 150) !=
        ESP_OK)
      return false;
    drain();
    if (expected != generation())
      return false;
    primed = expected;
  }
  if (expected != generation()) {
    return false;
  }
  gpio_set_level(BSP_POWER_AMP_IO, 1);
  for (size_t i = 0; i < samples; i += 160) {
    if (expected != generation()) {
      gpio_set_level(BSP_POWER_AMP_IO, 0);
      return false;
    }
    size_t count = std::min<size_t>(160, samples - i);
    int32_t stereo[320];
    for (size_t j = 0; j < count; ++j)
      stereo[j * 2] = stereo[j * 2 + 1] =
          static_cast<int32_t>(mono[i + j]) * 65536;
    size_t sent = 0;
    if (i2s_channel_write(tx, stereo, count * 8, &sent, 100) != ESP_OK ||
        sent != count * 8) {
      silence();
      return false;
    }
  }
  return expected == generation();
}
} // namespace board
