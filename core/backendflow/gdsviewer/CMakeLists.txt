cmake_minimum_required(VERSION 3.16)
project(silis_gds3d_viewer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets OpenGL OpenGLWidgets)
find_package(pybind11 REQUIRED)

include_directories(
    include
    ${Qt6Core_INCLUDE_DIRS}
    ${Qt6Gui_INCLUDE_DIRS}
    ${Qt6Widgets_INCLUDE_DIRS}
    ${Qt6OpenGL_INCLUDE_DIRS}
    ${Qt6OpenGLWidgets_INCLUDE_DIRS}
)

pybind11_add_module(silis_gds3d_viewer
    include/SilisNative3DViewer.h
    src/SilisNative3DViewer.cpp
    src/bindings.cpp
)

target_link_libraries(silis_gds3d_viewer PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::OpenGL
    Qt6::OpenGLWidgets
)

set_target_properties(silis_gds3d_viewer PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
)
