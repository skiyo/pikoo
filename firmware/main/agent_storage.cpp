// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#include "agent_storage.hpp"
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
  ~Handle() {
    if (value)
      nvs_close(value);
  }
  bool open(const char *part, nvs_open_mode_t mode) {
    return nvs_open_from_partition(part, Namespace, mode, &value) == ESP_OK;
  }
  std::string blob(const char *key, size_t limit) {
    size_t size = 0;
    if (nvs_get_blob(value, key, nullptr, &size) != ESP_OK || !size ||
        size > limit)
      return {};
    std::string result(size, '\0');
    return nvs_get_blob(value, key, result.data(), &size) == ESP_OK
               ? result
               : std::string{};
  }
  bool save(const char *key, const std::string &payload) {
    return nvs_set_blob(value, key, payload.data(), payload.size()) == ESP_OK &&
           nvs_commit(value) == ESP_OK;
  }
};

bool init_secrets() {
  return nvs_flash_init_partition(SecretPartition) == ESP_OK;
}

bool use_slot(Handle &h, uint8_t &slot) {
  return nvs_get_u8(h.value, "current", &slot) == ESP_OK && slot < 2;
}
} // namespace

bool load_agent_config(AgentConfig &out) {
  Handle h;
  if (!init_secrets() || !h.open(SecretPartition, ReadOnly))
    return false;
  auto payload = h.blob("config", AgentConfig::Limit);
  std::string error;
  const bool ok = decode_config(payload, out, error);
  mbedtls_platform_zeroize(payload.data(), payload.size());
  return ok;
}
bool provision_agent(const std::string &payload) {
  AgentConfig config;
  std::string error;
  if (!decode_config(payload, config, error))
    return false;
  Handle h;
  return init_secrets() && h.open(SecretPartition, Write) &&
         h.save("config", payload);
}
bool forget_agent_credentials() {
  Handle h;
  if (!init_secrets() || !h.open(SecretPartition, Write))
    return false;
  for (const char *key : {"config", "credentials"}) {
    auto r = nvs_erase_key(h.value, key);
    if (r != ESP_OK && r != ESP_ERR_NVS_NOT_FOUND)
      return false;
  }
  return nvs_commit(h.value) == ESP_OK;
}

bool init_family_store(FamilyStore &store) {
  Handle h;
  if (nvs_flash_init_partition(DataPartition) != ESP_OK ||
      !h.open(DataPartition, Write))
    return false;
  uint8_t slot = 0;
  if (!use_slot(h, slot))
    return true;
  return store.load(h.blob(slot ? "b" : "a", FamilyStore::Capacity)) ||
         store.load(h.blob(slot ? "a" : "b", FamilyStore::Capacity));
}

bool write_family_snapshot(const std::string &snapshot) {
  Handle h;
  if (!h.open(DataPartition, Write))
    return false;
  uint8_t slot = 1;
  use_slot(h, slot);
  slot ^= 1;
  return h.save(slot ? "b" : "a", snapshot) &&
         nvs_set_u8(h.value, "current", slot) == ESP_OK &&
         nvs_commit(h.value) == ESP_OK;
}

bool import_family_snapshot(FamilyStore &store, const std::string &snapshot) {
  FamilyStore test(write_family_snapshot);
  return test.load(snapshot) && write_family_snapshot(test.snapshot()) &&
         store.load(test.snapshot());
}
} // namespace pikoo
