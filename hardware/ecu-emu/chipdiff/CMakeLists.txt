# Chip-in-isolation test of the real D151801 against the emulator (docs/hardware/chip_diff_test.md):
#   cmake -B build -DPICO_BOARD=pico2_w && cmake --build build
# The Pico clocks the chip, plays the engine around it one E cycle at a time (chipdiff.h, the
# loopback's engine model) and logs every pin change over USB for analysis/emu/chipdiff.py.
cmake_minimum_required(VERSION 3.13)

set(PICO_PLATFORM rp2350)
include(pico_sdk_import.cmake)
project(ecu_chipdiff C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(ecu_chipdiff main.c ../core/hd6301.c ../core/d151801.c ../core/board.c)
pico_generate_pio_header(ecu_chipdiff ${CMAKE_CURRENT_LIST_DIR}/chipdiff.pio)
target_include_directories(ecu_chipdiff PRIVATE ../core ../loopback .)
target_compile_options(ecu_chipdiff PRIVATE -O2 -Wall -Wextra -Werror -Wno-unused-function)
target_link_libraries(ecu_chipdiff pico_stdlib pico_multicore hardware_pio hardware_dma)
pico_set_binary_type(ecu_chipdiff copy_to_ram)
pico_enable_stdio_usb(ecu_chipdiff 1)
pico_enable_stdio_uart(ecu_chipdiff 0)
pico_add_extra_outputs(ecu_chipdiff)
set_target_properties(ecu_chipdiff PROPERTIES OUTPUT_NAME ecu_chipdiff_${PICO_BOARD})
