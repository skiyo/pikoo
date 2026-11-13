// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
#pragma once
#include "pikoo_agent.hpp"
#include <cstdint>
#include <string>

namespace pikoo {
bool load_agent_config(AgentConfig &out);
bool provision_agent(const std::string &payload);
bool forget_agent_credentials();
bool init_family_store(FamilyStore &store);
bool write_family_snapshot(const std::string &snapshot);
bool import_family_snapshot(FamilyStore &store, const std::string &snapshot);
}
