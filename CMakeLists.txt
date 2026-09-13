cmake_minimum_required(VERSION 3.16)

project(
    PiDecoder
    VERSION 0.9.9.5
    DESCRIPTION "Low-latency RTSP video decoder for Raspberry Pi"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
find_package(OpenGL REQUIRED)
find_package(nlohmann_json 3.2.0 REQUIRED)

pkg_check_modules(SDL2 REQUIRED IMPORTED_TARGET sdl2)
pkg_check_modules(MPV REQUIRED IMPORTED_TARGET mpv)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/include/pidecoder/Version.hpp.in
    ${CMAKE_CURRENT_BINARY_DIR}/generated/pidecoder/Version.hpp
    @ONLY
)

add_executable(
    pidecoder
    src/main.cpp
    src/Application.cpp
    src/PtzController.cpp
    src/Config.cpp
    src/Window.cpp
    src/Player.cpp
    src/Renderer.cpp
    src/Grid.cpp
    src/Layout.cpp
)

target_include_directories(
    pidecoder
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_BINARY_DIR}/generated
)

target_link_libraries(
    pidecoder
    PRIVATE
        PkgConfig::SDL2
        PkgConfig::MPV
        OpenGL::GL
        nlohmann_json::nlohmann_json
)

target_compile_definitions(
    pidecoder
    PRIVATE
        GL_GLEXT_PROTOTYPES
)

target_compile_options(
    pidecoder
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wshadow
)

set_target_properties(
    pidecoder
    PROPERTIES
        BUILD_RPATH "/usr/local/lib/aarch64-linux-gnu;/usr/local/lib"
        INSTALL_RPATH "/usr/local/lib/aarch64-linux-gnu;/usr/local/lib"
)

install(
    TARGETS pidecoder
    RUNTIME DESTINATION bin
)
