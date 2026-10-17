#pragma once
#include "driver/gpio.h"
#include "esp_err.h"
#include "pikoo_eyes.hpp"
namespace board {
constexpr const char *Name = "waveshare-dualeye-1.28";
constexpr gpio_num_t Button = GPIO_NUM_0, Amp = GPIO_NUM_9;
constexpr gpio_num_t Sda = GPIO_NUM_11, Scl = GPIO_NUM_10;
constexpr gpio_num_t Mclk = GPIO_NUM_12, Bclk = GPIO_NUM_13, Ws = GPIO_NUM_14;
constexpr gpio_num_t Din = GPIO_NUM_15, Dout = GPIO_NUM_16;
esp_err_t display_init();
void display_frame(const pikoo::eyes::Pose &pose, const char *label);
float display_fps();
void display_rotation(int degrees);
uint32_t display_render_us();
uint32_t display_transfer_us();
}
