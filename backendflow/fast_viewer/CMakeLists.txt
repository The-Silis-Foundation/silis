cmake_minimum_required(VERSION 3.16)
project(FastLayoutViewer VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Widgets)
find_package(pybind11 REQUIRED)

pybind11_add_module(fast_layout_viewer bindings.cpp FastLayoutViewer.cpp)
target_link_libraries(fast_layout_viewer PRIVATE Qt6::Core Qt6::Widgets)
