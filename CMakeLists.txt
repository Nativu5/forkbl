cmake_minimum_required(VERSION 3.24)
project(ForkBL)

# Set C++ standard
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static libs" FORCE)

# Define the executable
add_executable(ForkBL main.cpp)

# Install prefix
if (WIN32 AND NOT DEFINED CMAKE_INSTALL_PREFIX)
   set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}/_install" CACHE PATH "Install prefix" FORCE)
endif()

# FetchContent for Zlib
set(SKIP_INSTALL_ALL ON CACHE BOOL "Disable zlib installation" FORCE)
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

# Install ForkBL.exe to the top-level of the ZIP
install(TARGETS ForkBL
    RUNTIME DESTINATION .
)

# Install config.json to the top-level of the ZIP
install(FILES
    "${CMAKE_SOURCE_DIR}/etc/config.json"
    DESTINATION .
)

# Install the entire scripts/ folder
install(DIRECTORY
    "${CMAKE_SOURCE_DIR}/scripts/"
    DESTINATION scripts
)

# Basic package info
set(CPACK_PACKAGE_NAME "ForkBL")
set(CPACK_PACKAGE_VERSION "0.1.0")

# Generate a .zip (you can add "TGZ" if you also want tar.gz)
set(CPACK_GENERATOR "ZIP")

# The final package file name, e.g. ForkBL-0.1.0-win64.zip
set(CPACK_PACKAGE_FILE_NAME "${CPACK_PACKAGE_NAME}-${CPACK_PACKAGE_VERSION}-win64")

# Optionally exclude a top-level directory inside the archive
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY OFF)

include(CPack)