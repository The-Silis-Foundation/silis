cmake_minimum_required(VERSION 3.10)
project(SilisDefViewer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt5 COMPONENTS Core Gui Widgets REQUIRED)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

add_executable(silis_def_viewer
    main.cpp
    LayoutViewer.h LayoutViewer.cpp
    RenderThread.h RenderThread.cpp
)

target_link_libraries(silis_def_viewer Qt5::Core Qt5::Gui Qt5::Widgets)
