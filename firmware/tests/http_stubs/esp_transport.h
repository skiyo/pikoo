#pragma once
#include <cstddef>
struct MockTransport;
using esp_transport_handle_t = MockTransport*;
constexpr int ERR_TCP_TRANSPORT_CONNECTION_CLOSED_BY_FIN = -9;
int esp_transport_destroy(esp_transport_handle_t);
int esp_transport_poll_read(esp_transport_handle_t,int);
int esp_transport_connect(esp_transport_handle_t,const char*,int,int);
int esp_transport_write(esp_transport_handle_t,const char*,int,int);
int esp_transport_read(esp_transport_handle_t,char*,int,int);
