cmake_minimum_required(VERSION 3.16)
project(editor_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

set(CMAKE_BUILD_RPATH "$ORIGIN;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib")
set(CMAKE_INSTALL_RPATH "$ORIGIN;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--disable-new-dtags")

find_package(Qt6 COMPONENTS Core Gui Widgets WebEngineWidgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(editor_engine bindings_editor.cpp MonacoViewer.cpp MonacoViewer.h)
target_link_libraries(editor_engine PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets Qt6::WebEngineWidgets)

add_custom_command(TARGET editor_engine POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:editor_engine> ${CMAKE_CURRENT_SOURCE_DIR}/
)
