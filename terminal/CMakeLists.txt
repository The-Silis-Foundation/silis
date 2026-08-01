cmake_minimum_required(VERSION 3.16)
project(terminal_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 COMPONENTS Core Gui Widgets REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(terminal_engine
    bindings_terminal.cpp
    TerminalWidget.cpp
    TerminalWidget.h
)

target_include_directories(terminal_engine PRIVATE
    ${CMAKE_SOURCE_DIR}/../schematicviewer  # reuse bundled json.hpp
)

target_link_libraries(terminal_engine PRIVATE
    Qt6::Core Qt6::Gui Qt6::Widgets
)
