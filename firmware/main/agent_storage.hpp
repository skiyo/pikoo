// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "pikoo_agent.hpp"
#include <cstdint>
#include <string>

namespace pikoo {
struct AgentCredentials {
  std::string proxy_host, proxy_basic, api_key;
  uint16_t proxy_port = 0;
  unsigned audio_rate = pikoo::LiveAgent::Rate;
  bool valid() const;
};
bool agent_enabled();
bool set_agent_mode(bool enabled);
bool load_agent_credentials(AgentCredentials &out);
bool provision_agent(const std::string &payload);
bool init_family_store(FamilyStore &store);
bool write_family_snapshot(const std::string &snapshot);
bool import_family_snapshot(FamilyStore &store, const std::string &snapshot);
}
