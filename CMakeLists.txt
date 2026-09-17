cmake_minimum_required(VERSION 3.16)

project(
    PiDecoder
    VERSION 1.2.0
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

# Renseignés par install.sh (mêmes valeurs que build-info.json, voir ce
# script) pour que le titre de la fenêtre du moteur natif affiche le même
# identifiant de build que la page Web administrateur — sans ça, deux
# affichages de "version" dans la même application qui ne se recoupent
# jamais (retour terrain : voir CHANGELOG.md). Vides par défaut : une
# compilation manuelle sans passer par install.sh (développement local,
# ni Git ni cette valeur transmise) affiche simplement le numéro de
# version seul, comme avant.
set(PIDECODER_BUILD_COMMIT "" CACHE STRING "Hash Git court du commit installé (renseigné par install.sh)")
set(PIDECODER_BUILD_STAMP "" CACHE STRING "Horodatage de l'installation, format AAMMJJHHMM (renseigné par install.sh)")

if(PIDECODER_BUILD_COMMIT AND PIDECODER_BUILD_STAMP)
    set(PIDECODER_BUILD_METADATA "+${PIDECODER_BUILD_COMMIT}.${PIDECODER_BUILD_STAMP}")
elseif(PIDECODER_BUILD_COMMIT)
    set(PIDECODER_BUILD_METADATA "+${PIDECODER_BUILD_COMMIT}")
else()
    set(PIDECODER_BUILD_METADATA "")
endif()

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
    src/RedactUrl.cpp
    src/NetworkInfo.cpp
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

# Garde-fou : petite suite de tests unitaires pour Layout/Grid (logique pure,
# sans SDL2/mpv). Activée par défaut mais désactivable si besoin, par ex.
# pour accélérer une compilation sur le Pi.
option(
    PIDECODER_BUILD_TESTS
    "Compiler les tests unitaires (Layout/Grid)"
    ON
)

if(PIDECODER_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
