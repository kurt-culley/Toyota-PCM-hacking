# Loopback test of the real-time emulator on one Pico 2 W, no wiring (docs/mr2/cpu_replacement.md):
#   cmake -B build -DPICO_BOARD=pico2_w && cmake --build build
# Core 1 runs the emulated D151801 with the 17140 ROM locked to real time; core 0 plays the
# engine on GPIO pins and measures the emulator's outputs through the same pads.
cmake_minimum_required(VERSION 3.13)

set(PICO_PLATFORM rp2350)
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/pico_sdk_import.cmake)
project(ecu_emu_loopback C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

file(READ "${CMAKE_CURRENT_LIST_DIR}/../../../roms/mr2_17140/89661-17140.bin" ROM_HEX HEX)
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," ROM_ARRAY "${ROM_HEX}")
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/rom17140.h "static const unsigned char ROM17140[4096] = {${ROM_ARRAY}};\n")

add_executable(ecu_emu_loopback main.c ../core/hd6301.c ../core/d151801.c ../core/board.c)
target_include_directories(ecu_emu_loopback PRIVATE ../core ${CMAKE_CURRENT_BINARY_DIR})
target_compile_options(ecu_emu_loopback PRIVATE -O2 -Wall -Wextra -Werror)
target_link_libraries(ecu_emu_loopback pico_stdlib pico_multicore hardware_timer)
pico_set_binary_type(ecu_emu_loopback copy_to_ram)
pico_enable_stdio_usb(ecu_emu_loopback 1)
pico_enable_stdio_uart(ecu_emu_loopback 0)
pico_add_extra_outputs(ecu_emu_loopback)
set_target_properties(ecu_emu_loopback PROPERTIES OUTPUT_NAME ecu_emu_loopback_${PICO_BOARD})
