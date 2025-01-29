cmake_minimum_required(VERSION 3.24)
project(ForkBL)

# Set C++ standard
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static libs" FORCE)

# Define the executable
add_executable(ForkBL main.cpp)

# FetchContent for Zlib
include(FetchContent)
FetchContent_Declare(
    zlib
    GIT_REPOSITORY https://github.com/madler/zlib.git
    GIT_TAG        v1.3.1
)
FetchContent_MakeAvailable(zlib)
target_link_libraries(ForkBL PRIVATE zlibstatic)

# FetchContent for nlohmann/json
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)
target_link_libraries(ForkBL PRIVATE nlohmann_json::nlohmann_json)

# Platform-specific configurations
if (WIN32)
    target_compile_definitions(ForkBL PRIVATE _WIN32_WINNT=0x0601)
    target_link_libraries(ForkBL PRIVATE ws2_32)
elseif (APPLE)
    find_library(CORE_FOUNDATION CoreFoundation)
    if (CORE_FOUNDATION)
        target_link_libraries(ForkBL PRIVATE ${CORE_FOUNDATION})
    endif()
endif()

# Add install rules
install(TARGETS ForkBL RUNTIME DESTINATION bin)
