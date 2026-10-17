// Original Pikoo integration for Waveshare ESP32-S3-DualEye-LCD-1.28.
#include "board_audio.hpp"
#include "board.hpp"
#include "pikoo_audio_slots.hpp"
#include "driver/i2c_master.h"
#include "driver/i2s_std.h"
#include "esp_codec_dev_defaults.h"
#include "esp_timer.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <mutex>
namespace board {
static i2s_chan_handle_t tx, rx;
static const audio_codec_if_t *dac, *adc;
static std::atomic<uint32_t> epoch{0};
static std::atomic<bool> collecting{true};
static std::atomic<float> mic_level{0}, ref_level{0}, out_level{0};
static std::atomic<float> mic_max{0}, ref_max{0};
static std::atomic<uint32_t> read_errors{0}, write_errors{0};
static std::atomic<int64_t> last_write{0};
static std::atomic<bool> amp_on{false};
static uint32_t primed=UINT32_MAX;
static std::mutex rx_mutex;
static std::atomic<int> volume{-24},volume_reg{-1};
esp_err_t audio_init() {
  gpio_config_t g{};g.pin_bit_mask=1ULL<<Amp;g.mode=GPIO_MODE_OUTPUT;
  ESP_ERROR_CHECK(gpio_config(&g));gpio_set_level(Amp,0);
  i2c_master_bus_handle_t bus;
  i2c_master_bus_config_t b{};b.i2c_port=I2C_NUM_0;b.sda_io_num=Sda;b.scl_io_num=Scl;
  b.clk_source=I2C_CLK_SRC_DEFAULT;b.glitch_ignore_cnt=7;b.flags.enable_internal_pullup=true;
  ESP_ERROR_CHECK(i2c_new_master_bus(&b,&bus));
  ESP_ERROR_CHECK(i2c_master_probe(bus,0x18,100));
  ESP_ERROR_CHECK(i2c_master_probe(bus,0x40,100));
  i2s_chan_config_t ch=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0,I2S_ROLE_MASTER);
  ch.dma_desc_num=4;ch.dma_frame_num=160;ch.auto_clear=true;
  ESP_ERROR_CHECK(i2s_new_channel(&ch,&tx,&rx));
  i2s_std_config_t cfg{};cfg.clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(16000);
  // Two 32-clock slots share clocks with the 16-bit DAC. In ES7210 TDM I2S
  // mode each left slot contains ADC1 then ADC3, not ADC1 then ADC2.
  cfg.slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT,I2S_SLOT_MODE_STEREO);
  cfg.gpio_cfg.mclk=Mclk;cfg.gpio_cfg.bclk=Bclk;cfg.gpio_cfg.ws=Ws;
  cfg.gpio_cfg.dout=Dout;cfg.gpio_cfg.din=Din;
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx,&cfg));
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx,&cfg));
  ESP_ERROR_CHECK(i2s_channel_enable(tx));ESP_ERROR_CHECK(i2s_channel_enable(rx));
  audio_codec_i2c_cfg_t cc{};cc.port=0;cc.bus_handle=bus;cc.addr=ES8311_CODEC_DEFAULT_ADDR;
  es8311_codec_cfg_t dc{};dc.ctrl_if=audio_codec_new_i2c_ctrl(&cc);
  dc.codec_mode=ESP_CODEC_DEV_WORK_MODE_DAC;dc.pa_pin=-1;dc.use_mclk=true;
  dac=es8311_codec_new(&dc);
  cc.addr=ES7210_CODEC_DEFAULT_ADDR;
  es7210_codec_cfg_t ac{};ac.ctrl_if=audio_codec_new_i2c_ctrl(&cc);
  // Board schematic: MIC1=physical microphone, MIC3=attenuated amplifier output reference.
  // Selecting four ADCs enables TDM I2S in esp_codec_dev. ADC2/4 are unused.
  ac.mic_selected=ES7210_SEL_MIC1|ES7210_SEL_MIC2|ES7210_SEL_MIC3|ES7210_SEL_MIC4;
  adc=es7210_codec_new(&ac);
  if(!dac||!adc) return ESP_FAIL;
  esp_codec_dev_sample_info_t fs{};fs.sample_rate=16000;fs.channel=2;fs.bits_per_sample=16;
  ESP_ERROR_CHECK(dac->set_fs(dac,&fs));
  fs.channel=4;ESP_ERROR_CHECK(adc->set_fs(adc,&fs));
  nvs_handle_t saved;
  if(nvs_open("pikoo",NVS_READONLY,&saved)==ESP_OK){
    int32_t level=-24;
    if(nvs_get_i32(saved,"volume_db",&level)==ESP_OK&&level>=-50&&level<=-6)volume=level;
    nvs_close(saved);
  }
  ESP_ERROR_CHECK(dac->enable(dac,true));ESP_ERROR_CHECK(dac->set_vol(dac,volume.load()));
  int reg=-1;if(dac->get_reg(dac,0x32,&reg)==ESP_OK)volume_reg=reg;
  ESP_ERROR_CHECK(adc->enable(adc,true));
  // enable() reapplies the codec's defaults; channel gains must follow it.
  ESP_ERROR_CHECK(adc->set_mic_gain(adc,0));
  ESP_ERROR_CHECK(adc->set_mic_channel_gain(adc,1,30));
  ESP_ERROR_CHECK(adc->set_mic_channel_gain(adc,4,24));
  return ESP_OK;
}
void capture_enabled(bool enabled) {
  std::lock_guard<std::mutex> lock(rx_mutex);
  if(collecting==enabled) return;
  collecting=enabled;
  if(enabled) {adc->enable(adc,true);adc->set_mic_gain(adc,0);adc->set_mic_channel_gain(adc,1,30);adc->set_mic_channel_gain(adc,4,24);i2s_channel_enable(rx);}
  else {i2s_channel_disable(rx);adc->enable(adc,false);mic_level=0;ref_level=0;}
}
bool capture(int16_t *mr,size_t frames) {
  std::lock_guard<std::mutex> lock(rx_mutex);
  if(!collecting) return false;
  // Full-duplex AFE consumes 512 frames (VC used 256). Keep its larger
  // interleaved capture block off the audio task's stack.
  static std::array<int32_t,1024> raw{};
  if(frames>raw.size()/2)return false;
  size_t bytes=0;
  if(i2s_channel_read(rx,raw.data(),frames*8,&bytes,100)!=ESP_OK||bytes!=frames*8){++read_errors;return false;}
  float m=0,r=0;
  for(size_t i=0;i<frames;i++){
    pikoo::es7210_mr(raw[2*i],mr[2*i],mr[2*i+1]);
    m+=float(mr[2*i])*mr[2*i];r+=float(mr[2*i+1])*mr[2*i+1];
  }
  mic_level=std::sqrt(m/frames)/32768.f;ref_level=std::sqrt(r/frames)/32768.f;
  mic_max=std::max(mic_max.load(),mic_level.load());
  ref_max=std::max(ref_max.load(),ref_level.load());
  return true;
}
void silence(){++epoch;gpio_set_level(Amp,0);amp_on=false;out_level=0;}
uint32_t generation(){return epoch.load();}
void drain(){vTaskDelay(pdMS_TO_TICKS(50));}
void playback_idle(bool keep_ready){
  if(esp_timer_get_time()-last_write>60000){
    out_level=0;
    if(!keep_ready){gpio_set_level(Amp,0);amp_on=false;}
  }
}
bool prepare_playback(uint32_t expected) {
  if(expected!=generation()) return false;
  if(primed!=expected){
    std::array<int32_t,320> zeros{};
    for(int i=0;i<6;i++){size_t n=0;if(i2s_channel_write(tx,zeros.data(),sizeof(zeros),&n,100)!=ESP_OK){++write_errors;return false;}}
    drain();if(expected!=generation()) return false;primed=expected;
  }
  if(!amp_on){
    // Enable the amplifier while I2S is still silent. Do not spend its
    // settling interval on the first phoneme of the response.
    gpio_set_level(Amp,1);amp_on=true;
    std::array<int32_t,320> zeros{};
    for(int i=0;i<3;i++){
      if(expected!=generation()){gpio_set_level(Amp,0);amp_on=false;return false;}
      size_t n=0;
      if(i2s_channel_write(tx,zeros.data(),sizeof(zeros),&n,100)!=ESP_OK||n!=sizeof(zeros)){++write_errors;silence();return false;}
    }
    last_write=esp_timer_get_time();
  }
  return expected==generation();
}
bool play(const int16_t *mono,size_t samples,uint32_t expected) {
  if(!prepare_playback(expected))return false;
  for(size_t i=0;i<samples;i+=160){
    if(expected!=generation()){gpio_set_level(Amp,0);amp_on=false;return false;}
    size_t count=std::min<size_t>(160,samples-i);int32_t stereo[320];float power=0;
    for(size_t j=0;j<count;j++){stereo[2*j]=stereo[2*j+1]=pikoo::dac_slot(mono[i+j]);power+=float(mono[i+j])*mono[i+j];}
    out_level=std::sqrt(power/count)/32768.f;
    size_t sent=0;
    if(i2s_channel_write(tx,stereo,count*8,&sent,100)!=ESP_OK||sent!=count*8){++write_errors;silence();return false;}
    last_write=esp_timer_get_time();
  }
  return expected==generation();
}
float microphone_level(){return mic_level;}
float reference_level(){return ref_level;}
float microphone_peak(){return mic_max.exchange(0);}
float reference_peak(){return ref_max.exchange(0);}
float output_level(){return out_level;}
uint32_t capture_errors(){return read_errors;}
uint32_t playback_errors(){return write_errors;}
esp_err_t set_volume(int db){
  if(db < -50 || db > -6)return ESP_ERR_INVALID_ARG;
  auto result=dac->set_vol(dac,db);if(result!=ESP_OK)return result;
  volume=db;int reg=-1;if(dac->get_reg(dac,0x32,&reg)==ESP_OK)volume_reg=reg;
  nvs_handle_t saved;
  if(nvs_open("pikoo",NVS_READWRITE,&saved)==ESP_OK){nvs_set_i32(saved,"volume_db",db);nvs_commit(saved);nvs_close(saved);}
  return ESP_OK;
}
int volume_db(){return volume.load();}
int volume_register(){return volume_reg.load();}
} // namespace board
