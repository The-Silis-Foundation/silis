cmake_minimum_required(VERSION 3.16)
project(schematic_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

set(CMAKE_BUILD_RPATH "$ORIGIN;/home/eatheswar/.local/lib/python3.12/site-packages/PyQt6/Qt6/lib;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu")
set(CMAKE_INSTALL_RPATH "$ORIGIN;/home/eatheswar/.local/lib/python3.12/site-packages/PyQt6/Qt6/lib;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--disable-new-dtags")

find_package(Qt6 COMPONENTS Core Gui Widgets WebEngineWidgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(schematic_engine bindings_schematic.cpp SchematicViewer.cpp SchematicViewer.h YosysWorker.cpp YosysWorker.h)
target_link_libraries(schematic_engine PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets Qt6::WebEngineWidgets)

add_custom_command(TARGET schematic_engine POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:schematic_engine> ${CMAKE_CURRENT_SOURCE_DIR}/
)

