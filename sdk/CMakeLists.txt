# HB_EVENT C library and examples
# Build: mkdir build && cd build && cmake .. && make
# Output: libhb_event.a, libhb_event.so, examples/send_event, examples/receive_ack

cmake_minimum_required(VERSION 3.10)
project(hb_event C)

set(CMAKE_C_STANDARD 11)

# Library (static and shared)
add_library(hb_event STATIC hb_event.c)
add_library(hb_event_shared SHARED hb_event.c)
set_target_properties(hb_event_shared PROPERTIES OUTPUT_NAME hb_event PREFIX "")

# Install
install(TARGETS hb_event hb_event_shared
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib)
install(FILES hb_event.h DESTINATION include)

# Examples (optional; built in examples/cpp with C++ compiler)
# This top-level only builds the C lib.
