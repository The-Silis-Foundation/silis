cmake_minimum_required(VERSION 3.16)
project(FastLayoutViewer VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets)
find_package(pybind11 REQUIRED)

set(CMAKE_BUILD_RPATH "$ORIGIN;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib")
set(CMAKE_INSTALL_RPATH "$ORIGIN;/home/eatheswar/.local/usr/lib/x86_64-linux-gnu;/usr/local/lib/python3.12/dist-packages/PyQt6/Qt6/lib")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--disable-new-dtags")

pybind11_add_module(fast_layout_viewer bindings.cpp FastLayoutViewer.cpp)
target_link_libraries(fast_layout_viewer PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets)

add_custom_command(TARGET fast_layout_viewer POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:fast_layout_viewer> ${CMAKE_CURRENT_SOURCE_DIR}/
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:fast_layout_viewer> ${CMAKE_CURRENT_SOURCE_DIR}/../siliconpeeker/
)
