cmake_minimum_required(VERSION 3.16)
project(silis_layer_viewer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)
find_package(pybind11 REQUIRED)

include_directories(
    include
    ${Qt6Core_INCLUDE_DIRS}
    ${Qt6Gui_INCLUDE_DIRS}
    ${Qt6Widgets_INCLUDE_DIRS}
)

pybind11_add_module(silis_layer_viewer
    include/SilisNativeLayerViewer.h
    src/SilisNativeLayerViewer.cpp
    src/bindings.cpp
)

target_link_libraries(silis_layer_viewer PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
)

# Output directly into the layer_viewer directory for immediate python ingestion
set_target_properties(silis_layer_viewer PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)
