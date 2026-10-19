// Original board integration; pin assignments follow the Waveshare non-touch board.
#include "board.hpp"
#include "driver/spi_master.h"
#include "esp_heap_caps.h"
#include "esp_lcd_gc9a01.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <algorithm>
#include <atomic>
#include <cstring>
namespace board {
namespace {
constexpr int StripeRows=60;
esp_lcd_panel_handle_t panels[2];
SemaphoreHandle_t complete[2];
uint16_t *pixels;
uint16_t *strip;
std::atomic<float> fps{0};
std::atomic<int> rotation{90};
int applied_rotation=-1;
std::atomic<uint32_t> render_us{0},transfer_us{0};
uint64_t frame_start = 0;
unsigned frames = 0;
bool previous_sleeping=false;
pikoo::eyes::RowRange previous_closed_rows{0,240};
bool done(esp_lcd_panel_io_handle_t, esp_lcd_panel_io_event_data_t *, void *ctx) {
  BaseType_t woken = pdFALSE;
  xSemaphoreGiveFromISR(static_cast<SemaphoreHandle_t>(ctx), &woken);
  return woken == pdTRUE;
}
// Small original 5x7 Latin status font. No bitmap assets or font dependencies.
const uint8_t *glyph(char c) {
  static const uint8_t font[][5] = {
    {0,0,0,0,0},{0x7e,0x11,0x11,0x11,0x7e},{0x7f,0x49,0x49,0x49,0x36},
    {0x3e,0x41,0x41,0x41,0x22},{0x7f,0x41,0x41,0x22,0x1c},{0x7f,0x49,0x49,0x49,0x41},
    {0x7f,9,9,9,1},{0x3e,0x41,0x49,0x49,0x7a},{0x7f,8,8,8,0x7f},{0,0x41,0x7f,0x41,0},
    {0x20,0x40,0x41,0x3f,1},{0x7f,8,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
    {0x7f,2,0xc,2,0x7f},{0x7f,4,8,0x10,0x7f},{0x3e,0x41,0x41,0x41,0x3e},
    {0x7f,9,9,9,6},{0x3e,0x41,0x51,0x21,0x5e},{0x7f,9,0x19,0x29,0x46},
    {0x46,0x49,0x49,0x49,0x31},{1,1,0x7f,1,1},{0x3f,0x40,0x40,0x40,0x3f},
    {0x1f,0x20,0x40,0x20,0x1f},{0x7f,0x20,0x18,0x20,0x7f},{0x63,0x14,8,0x14,0x63},
    {7,8,0x70,8,7},{0x61,0x51,0x49,0x45,0x43}};
  return font[c >= 'A' && c <= 'Z' ? c-'A'+1 : 0];
}
void text(const char *s) {
  if (!s || !*s) return;
  size_t n = std::min<size_t>(strlen(s), 17);
  int left = (240-int(n)*12)/2;
  for (size_t i=0;i<n;i++) for (int x=0;x<5;x++) for(int y=0;y<7;y++) {
    bool bit=glyph(s[i])[x] & (1<<y);
    for(int a=0;a<2;a++) for(int b=0;b<2;b++)
      pixels[(192+y*2+b)*240+left+i*12+x*2+a]=bit?0xff9d:0x2124;
  }
}
}
esp_err_t display_init() {
  gpio_config_t g{}; g.pin_bit_mask=(1ULL<<46)|(1ULL<<39); g.mode=GPIO_MODE_OUTPUT;
  ESP_ERROR_CHECK(gpio_config(&g)); gpio_set_level(GPIO_NUM_46,0); gpio_set_level(GPIO_NUM_39,0);
  spi_bus_config_t bus{}; bus.mosi_io_num=42; bus.miso_io_num=-1; bus.sclk_io_num=41;
  bus.quadwp_io_num=-1; bus.quadhd_io_num=-1; bus.max_transfer_sz=240*StripeRows*2;
  ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO));
  for(int i=0;i<2;i++) {
    complete[i]=xSemaphoreCreateBinary();
    if(!complete[i]) return ESP_ERR_NO_MEM;
    esp_lcd_panel_io_spi_config_t io{}; io.cs_gpio_num=i?38:47; io.dc_gpio_num=45;
    io.pclk_hz=80000000; io.lcd_cmd_bits=8; io.lcd_param_bits=8; io.trans_queue_depth=1;
    io.on_color_trans_done=done; io.user_ctx=complete[i];
    esp_lcd_panel_io_handle_t handle;
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI2_HOST,&io,&handle));
    esp_lcd_panel_dev_config_t config{}; config.reset_gpio_num=i?8:48;
    config.rgb_ele_order=LCD_RGB_ELEMENT_ORDER_BGR; config.bits_per_pixel=16;
    ESP_ERROR_CHECK(esp_lcd_new_panel_gc9a01(handle,&config,&panels[i]));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panels[i]));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panels[i]));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panels[i],true));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(panels[i],i==0,i==1));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panels[i],true));
  }
  pixels=static_cast<uint16_t*>(heap_caps_malloc(pikoo::eyes::EyePixels*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  strip=static_cast<uint16_t*>(heap_caps_malloc(240*StripeRows*2,MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA));
  if(!pixels||!strip) return ESP_ERR_NO_MEM;
  gpio_set_level(GPIO_NUM_46,1); gpio_set_level(GPIO_NUM_39,1);
  return ESP_OK;
}
void display_frame(const pikoo::eyes::Pose &pose,const char *label) {
  auto selected=rotation.load();
  const bool rotation_changed=selected!=applied_rotation;
  if(selected!=applied_rotation) {
    for(int eye=0;eye<2;eye++) {
      esp_lcd_panel_swap_xy(panels[eye],selected==90||selected==270);
      bool x=selected==90?eye==1:selected==270?eye==0:selected==0?eye==0:eye==1;
      bool y=selected==90?eye==1:selected==270?eye==0:selected==0?eye==1:eye==0;
      esp_lcd_panel_mirror(panels[eye],x,y);
    }
    applied_rotation=selected;
  }
  uint32_t drawing=0,transferring=0;
  const bool sleeping=pose.state==pikoo::eyes::State::Idle&&pose.open==0&&pose.ring==0&&pose.saturation==1&&(!label||!*label);
  // Once the transition has completed, the sleeping arcs only change inside
  // this band. Preserve the physical screen's background instead of sending
  // two complete 115 KiB frames for a sub-pixel breathing movement.
  const bool partial=sleeping&&previous_sleeping&&!rotation_changed;
  previous_sleeping=false;
  const auto closed_rows=pikoo::eyes::closed_eye_rows(pose);
  const int first=partial?std::min(previous_closed_rows.first,closed_rows.first):0;
  const int last=partial?std::max(previous_closed_rows.last,closed_rows.last):240;
  for(int eye=0;eye<2;eye++) {
    auto start=esp_timer_get_time();
    if(!pikoo::eyes::render_fast_rows(pose,eye,pixels,pikoo::eyes::EyePixels,first,last)) return;
    text(label);
    drawing+=esp_timer_get_time()-start;start=esp_timer_get_time();
    for(int y=first;y<last;y+=StripeRows) {
      const int rows=std::min(StripeRows,last-y);
      for(int i=0;i<240*rows;i++) strip[i]=__builtin_bswap16(pixels[y*240+i]);
      if(esp_lcd_panel_draw_bitmap(panels[eye],0,y,240,y+rows,strip)!=ESP_OK) return;
      if(!xSemaphoreTake(complete[eye],pdMS_TO_TICKS(500))) return;
    }
    transferring+=esp_timer_get_time()-start;
  }
  previous_sleeping=sleeping;
  previous_closed_rows=closed_rows;
  render_us=drawing;transfer_us=transferring;
  auto t=esp_timer_get_time(); if(!frame_start) frame_start=t;
  frames++;
  if(t-frame_start>=1000000) {fps=frames*1000000.f/(t-frame_start);frames=0;frame_start=t;}
}
float display_fps(){return fps.load();}
void display_rotation(int degrees){if(degrees==0||degrees==90||degrees==180||degrees==270)rotation=degrees;}
uint32_t display_render_us(){return render_us.load();}
uint32_t display_transfer_us(){return transfer_us.load();}
}
