cmake_minimum_required(VERSION 3.16)
project(schematic_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 COMPONENTS Core Gui Widgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(schematic_engine bindings_schematic.cpp SchematicViewer.cpp SchematicViewer.h SchematicRouter.cpp SchematicRouter.h YosysWorker.cpp YosysWorker.h)
target_link_libraries(schematic_engine PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets)
