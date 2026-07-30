cmake_minimum_required(VERSION 3.12)
project(fast_schem_parser)

# Find Pybind11
find_package(pybind11 REQUIRED)

# Create the shared module
pybind11_add_module(fast_schem_parser fast_schem_parser.cpp)
target_compile_features(fast_schem_parser PRIVATE cxx_std_17)
