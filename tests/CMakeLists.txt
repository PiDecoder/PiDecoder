# Garde-fou Layout/Grid : petite suite de tests sans framework externe
# (cohérent avec le reste du projet, qui reste volontairement léger en
# dépendances). Compile directement les .cpp réels de src/ pour tester le
# vrai code, pas une copie.

add_executable(
    pidecoder_tests
    test_main.cpp
    test_grid.cpp
    test_layout.cpp
    ${CMAKE_SOURCE_DIR}/src/Grid.cpp
    ${CMAKE_SOURCE_DIR}/src/Layout.cpp
)

target_include_directories(
    pidecoder_tests
    PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(
    pidecoder_tests
    PRIVATE
        nlohmann_json::nlohmann_json
)

target_compile_options(
    pidecoder_tests
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
)

add_test(
    NAME pidecoder_tests
    COMMAND pidecoder_tests
)
