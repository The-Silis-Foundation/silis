cmake_minimum_required(VERSION 3.16)
project(editor_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 COMPONENTS Core Gui Widgets WebEngineWidgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(editor_engine bindings_editor.cpp MonacoViewer.cpp MonacoViewer.h)
target_link_libraries(editor_engine PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets Qt6::WebEngineWidgets)
