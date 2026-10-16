# Speed test of the C HD6301 core on a Pico 2 W (docs/emulator/design.md):
#   cmake -B build -DPICO_BOARD=pico2_w && cmake --build build
# Runs the 17140 ROM (embedded at build time from roms/mr2_17140/89661-17140.bin) on the core
# with pseudo-random port reads, and prints how many times faster than the real 1 MHz chip it is.
cmake_minimum_required(VERSION 3.13)

set(PICO_PLATFORM rp2350)
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/pico_sdk_import.cmake)
project(ecu_emu_bench C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

# Embed the ROM image as a C array (the .bin stays the only copy in the repo).

file(READ "${CMAKE_CURRENT_LIST_DIR}/../../../roms/mr2_17140/89661-17140.bin" ROM_HEX HEX)
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," ROM_ARRAY "${ROM_HEX}")
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/rom17140.h "static const unsigned char ROM17140[4096] = {${ROM_ARRAY}};\n")

add_executable(ecu_emu_bench main.c ../core/hd6301.c)
target_include_directories(ecu_emu_bench PRIVATE ../core ${CMAKE_CURRENT_BINARY_DIR})
target_compile_options(ecu_emu_bench PRIVATE -O2 -Wall -Wextra -Werror)
target_link_libraries(ecu_emu_bench pico_stdlib)
pico_set_binary_type(ecu_emu_bench copy_to_ram)
pico_enable_stdio_usb(ecu_emu_bench 1)
pico_enable_stdio_uart(ecu_emu_bench 0)
pico_add_extra_outputs(ecu_emu_bench)
set_target_properties(ecu_emu_bench PROPERTIES OUTPUT_NAME ecu_emu_bench_${PICO_BOARD})
