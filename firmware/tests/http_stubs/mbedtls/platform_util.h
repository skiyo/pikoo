#pragma once
#include <cstddef>
inline void mbedtls_platform_zeroize(void* p,size_t n){volatile auto* q=static_cast<volatile unsigned char*>(p);while(n--)*q++=0;}
