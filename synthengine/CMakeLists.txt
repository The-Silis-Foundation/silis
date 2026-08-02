cmake_minimum_required(VERSION 3.16)
project(synthengine)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11.git
  GIT_TAG        v2.11.1
)
FetchContent_MakeAvailable(pybind11)

# Include OpenSTA from third-party so we can link against it
# We do not want to build the 'sta' executable to save time, but it's hardcoded in their CMakeLists.txt.
# It's fine, we'll just build the whole tree.
add_subdirectory(${CMAKE_SOURCE_DIR}/../third-party/OpenSTA ${CMAKE_BINARY_DIR}/OpenSTA_build)

pybind11_add_module(synth_engine 
    bindings_synth.cpp 
    SynthOrchestrator.cpp 
    TimingAnalyzer.cpp
)

target_include_directories(synth_engine PRIVATE 
    ${CMAKE_SOURCE_DIR}/../third-party/OpenSTA/include
    ${CMAKE_SOURCE_DIR}/../third-party/OpenSTA/app
    ${CMAKE_SOURCE_DIR}/../third-party/OpenSTA
)

# Link OpenSTA and its dependencies
target_link_libraries(synth_engine PRIVATE OpenSTA sta_swig tcl cudd)
