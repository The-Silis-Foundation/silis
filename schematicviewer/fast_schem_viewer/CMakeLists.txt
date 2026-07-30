cmake_minimum_required(VERSION 3.16)
project(fast_schem_viewer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 COMPONENTS Core Gui Widgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(fast_schem_viewer bindings_viewer.cpp FastSchematicViewer.cpp FastSchematicViewer.h)
target_link_libraries(fast_schem_viewer PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets)
