cmake_minimum_required(VERSION 3.16)
project(GDS3DEngine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_BUILD_TYPE Release)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native -ffast-math")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC OFF)
set(CMAKE_AUTORCC OFF)

find_package(Qt6 COMPONENTS Core Gui Widgets OpenGLWidgets REQUIRED)
find_package(pybind11 REQUIRED)
find_package(OpenMP)

if(OpenMP_CXX_FOUND)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
endif()

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/math
    ${CMAKE_CURRENT_SOURCE_DIR}/gdsoglviewer
    ${CMAKE_CURRENT_SOURCE_DIR}/libgdsto3d
)

# Collect all sources
file(GLOB_RECURSE GDS3D_SOURCES
    "math/*.cpp"
    "gdsoglviewer/*.cpp"
    "libgdsto3d/*.cpp"
    "libgdsto3d/clipper/*.cpp"
    "libgdsto3d/voro++/src/voro++.cc"
)

# Add Qt Wrapper and bindings
set(GDS3D_SOURCES
    ${GDS3D_SOURCES}
    GDS3DWidget.cpp
    bindings_gds3d.cpp
)

pybind11_add_module(gds3d_engine ${GDS3D_SOURCES})

target_link_libraries(gds3d_engine PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::OpenGLWidgets
)
