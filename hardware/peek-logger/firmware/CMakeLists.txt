# Serial-link logger for the MR2 89661-17140 ECU (docs/mr2/serial_link.md), Pico 2 W:
#   cmake -B build -DPICO_BOARD=pico2_w && cmake --build build
# Needs pico-sdk >= 2.1 (PICO_SDK_PATH) and arm-none-eabi-gcc. CI builds the UF2.
cmake_minimum_required(VERSION 3.13)

set(PICO_PLATFORM rp2350)
include(pico_sdk_import.cmake)
project(peek_logger C CXX ASM)
set(CMAKE_C_STANDARD 11)

if (PICO_SDK_VERSION_STRING VERSION_LESS "2.1.0")
    message(FATAL_ERROR "pico-sdk 2.1.0 or later is required (RP2350 A4 stepping support)")
endif()

pico_sdk_init()

add_executable(peek_logger src/main.c)
target_include_directories(peek_logger PRIVATE src)
target_compile_options(peek_logger PRIVATE -Wall -Wextra -Werror)
target_link_libraries(peek_logger pico_stdlib hardware_uart)
pico_enable_stdio_usb(peek_logger 1)
pico_enable_stdio_uart(peek_logger 0)
pico_add_extra_outputs(peek_logger)
set_target_properties(peek_logger PROPERTIES OUTPUT_NAME peek_logger_${PICO_BOARD})
