idf_component_register(SRCS "main.cpp" "board_audio.cpp" "wake_model.cpp" INCLUDE_DIRS "." REQUIRES pikoo_core pikoo_features nvs_flash esp_wifi esp_netif esp_event esp_timer json mbedtls esp_driver_i2s esp_driver_gpio esp_driver_uart)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
target_add_binary_data(${COMPONENT_LIB} "${PROJECT_DIR}/../training/models/nihao_pikoo.tflite" BINARY)
