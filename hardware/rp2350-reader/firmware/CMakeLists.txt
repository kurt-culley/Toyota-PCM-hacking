# HD6301 ROM reader firmware (P3). Build for each board:
#   cmake -B build-bb48 -DPICO_BOARD=olimex_rp2350_pico2_bb48 && cmake --build build-bb48
#   cmake -B build-pico2w -DPICO_BOARD=pico2_w && cmake --build build-pico2w
# Needs pico-sdk >= 2.1 (PICO_SDK_PATH) and arm-none-eabi-gcc. CI builds both UF2s.
cmake_minimum_required(VERSION 3.13)

list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
set(PICO_PLATFORM rp2350)
include(pico_sdk_import.cmake)
project(rp2350_reader C CXX ASM)
set(CMAKE_C_STANDARD 11)

if (PICO_SDK_VERSION_STRING VERSION_LESS "2.1.0")
    message(FATAL_ERROR "pico-sdk 2.1.0 or later is required (RP2350 A4 stepping support)")
endif()

pico_sdk_init()

add_executable(rp2350_reader src/main.c)
pico_generate_pio_header(rp2350_reader ${CMAKE_CURRENT_LIST_DIR}/src/reader.pio)
target_include_directories(rp2350_reader PRIVATE src)
target_compile_options(rp2350_reader PRIVATE -Wall -Wextra -Werror)
target_link_libraries(rp2350_reader pico_stdlib pico_multicore hardware_pio)
pico_enable_stdio_usb(rp2350_reader 1)
pico_enable_stdio_uart(rp2350_reader 0)
pico_add_extra_outputs(rp2350_reader)
set_target_properties(rp2350_reader PROPERTIES OUTPUT_NAME rp2350_reader_${PICO_BOARD})
