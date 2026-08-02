cmake_minimum_required(VERSION 3.16)
project(clocktree_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(Qt6 COMPONENTS Core Gui Widgets REQUIRED)

include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.11.1
)
FetchContent_MakeAvailable(pybind11)

pybind11_add_module(clocktree_engine bindings_clocktree.cpp ClockTreeViewer.cpp ClockTreeViewer.h)
target_link_libraries(clocktree_engine PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets)
