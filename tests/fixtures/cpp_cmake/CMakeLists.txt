cmake_minimum_required(VERSION 3.20)
project(EngineCore CXX)

set(CMAKE_CXX_STANDARD 17)

include_directories(include)
add_library(engine src/engine.cpp)
enable_testing()
