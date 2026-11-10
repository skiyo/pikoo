// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "agent_storage.hpp"
#include "esp_efuse.h"
#include "esp_hmac.h"
#include "mbedtls/platform_util.h"
#include "nvs_flash.h"
#include <algorithm>
#include <cctype>

namespace pikoo {
namespace {
constexpr char SecretPartition[] = "agent_secret";
constexpr char DataPartition[] = "agent_data";
constexpr char Namespace[] = "edge";
constexpr auto ReadOnly = NVS_READONLY;
constexpr auto Write = NVS_READWRITE;

struct Handle {
  nvs_handle_t value = 0;
  ~Handle() { if (value) nvs_close(value); }
  bool open(const char *part, nvs_open_mode_t mode) {
    return nvs_open_from_partition(part, Namespace, mode, &value) == ESP_OK;
  }
  std::string blob(const char *key, size_t limit) {
    size_t size = 0;
    if (nvs_get_blob(value, key, nullptr, &size) != ESP_OK || !size || size > limit) return {};
    std::string result(size, '\0');
    return nvs_get_blob(value, key, result.data(), &size) == ESP_OK ? result : std::string{};
  }
  bool save(const char *key, const std::string &payload) {
    return nvs_set_blob(value, key, payload.data(), payload.size()) == ESP_OK &&
      nvs_commit(value) == ESP_OK;
  }
};

bool init_secrets() {
  static const bool available = [] {
    esp_efuse_block_t block;
    if (!esp_efuse_find_purpose(ESP_EFUSE_KEY_PURPOSE_HMAC_UP, &block) ||
        block < EFUSE_BLK_KEY0 || block > EFUSE_BLK_KEY5) return false;
    // Distinct fixed labels produce two NVS XTS keys on this device. Never
    // provision or change eFuse from the application.
    const auto key = hmac_key_id_t(block - EFUSE_BLK_KEY0);
    constexpr char Encryption[] = "pikoo-agent-secret-xts-data-v1";
    constexpr char Tweak[] = "pikoo-agent-secret-xts-tweak-v1";
    nvs_sec_cfg_t config{};
    const bool ok = esp_hmac_calculate(key, Encryption, sizeof(Encryption) - 1, config.eky) == ESP_OK &&
      esp_hmac_calculate(key, Tweak, sizeof(Tweak) - 1, config.tky) == ESP_OK &&
      nvs_flash_secure_init_partition(SecretPartition, &config) == ESP_OK;
    mbedtls_platform_zeroize(&config, sizeof(config));
    return ok;
  }();
  return available;
}

bool decode(const std::string &payload, AgentCredentials &credentials) {
  auto data = parse(payload);
  auto port = field(data.get(), "proxy_port");
  if (!cJSON_IsNumber(port) || port->valuedouble < 1 || port->valuedouble > 65535 ||
      port->valueint != port->valuedouble) return false;
  const auto rate = field(data.get(), "audio_rate");
  if (rate && (!cJSON_IsNumber(rate) || (rate->valuedouble != 16000 && rate->valuedouble != 24000)))
    return false;
  credentials = {text(data.get(), "proxy_host"), text(data.get(), "proxy_basic"),
                 text(data.get(), "api_key"), uint16_t(port->valueint),
                 rate ? unsigned(rate->valueint) : LiveAgent::Rate};
  if (auto value = field(data.get(), "api_key"); cJSON_IsString(value))
    mbedtls_platform_zeroize(value->valuestring, credentials.api_key.size());
  if (auto value = field(data.get(), "proxy_basic"); cJSON_IsString(value))
    mbedtls_platform_zeroize(value->valuestring, credentials.proxy_basic.size());
  return credentials.valid();
}

bool use_slot(Handle &h, uint8_t &slot) {
  return nvs_get_u8(h.value, "current", &slot) == ESP_OK && slot < 2;
}
}

bool AgentCredentials::valid() const {
  return proxy_port && !proxy_host.empty() && proxy_host.size() <= 253 &&
    std::all_of(proxy_host.begin(), proxy_host.end(), [](unsigned char ch) {
      return std::isalnum(ch) || ch == '.' || ch == '-';
    }) && safe_header(proxy_basic) && safe_header(api_key);
}

bool agent_enabled() {
  Handle h;
  uint8_t enabled = 0;
  return h.open("nvs", ReadOnly) && nvs_get_u8(h.value, "local_agent", &enabled) == ESP_OK && enabled == 1;
}

bool set_agent_mode(bool enabled) {
  Handle h;
  return h.open("nvs", Write) && nvs_set_u8(h.value, "local_agent", enabled) == ESP_OK &&
    nvs_commit(h.value) == ESP_OK;
}

bool load_agent_credentials(AgentCredentials &out) {
  Handle h;
  if (!init_secrets() || !h.open(SecretPartition, ReadOnly)) return false;
  auto payload = h.blob("credentials", 4096);
  const bool ok = decode(payload, out);
  mbedtls_platform_zeroize(payload.data(), payload.size());
  return ok;
}

bool provision_agent(const std::string &payload) {
  if (payload.size() > 4096) return false;
  AgentCredentials credentials;
  const bool valid = decode(payload, credentials);
  mbedtls_platform_zeroize(credentials.api_key.data(), credentials.api_key.size());
  mbedtls_platform_zeroize(credentials.proxy_basic.data(), credentials.proxy_basic.size());
  Handle h;
  return valid && init_secrets() && h.open(SecretPartition, Write) &&
    h.save("credentials", payload) && set_agent_mode(true);
}

bool init_family_store(FamilyStore &store) {
  Handle h;
  if (nvs_flash_init_partition(DataPartition) != ESP_OK || !h.open(DataPartition, Write)) return false;
  uint8_t slot = 0;
  if (!use_slot(h, slot)) return true;
  return store.load(h.blob(slot ? "b" : "a", FamilyStore::Capacity)) ||
    store.load(h.blob(slot ? "a" : "b", FamilyStore::Capacity));
}

bool write_family_snapshot(const std::string &snapshot) {
  Handle h;
  if (!h.open(DataPartition, Write)) return false;
  uint8_t slot = 1;
  use_slot(h, slot);
  slot ^= 1;
  return h.save(slot ? "b" : "a", snapshot) &&
    nvs_set_u8(h.value, "current", slot) == ESP_OK && nvs_commit(h.value) == ESP_OK;
}

bool import_family_snapshot(FamilyStore &store, const std::string &snapshot) {
  FamilyStore test(write_family_snapshot);
  return test.load(snapshot) && write_family_snapshot(test.snapshot()) && store.load(test.snapshot());
}
}
