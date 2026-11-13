idf_component_register(SRCS "pikoo_agent.cpp" "pikoo_config.cpp" "pikoo_backend.cpp" "pikoo_http.cpp" INCLUDE_DIRS "include" REQUIRES json)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
