# In-car test firmware (docs/mr2/cpu_replacement.md, "In-car test rig"):
#   cmake -B build -DPICO_BOARD=pico2_w && cmake --build build
# The emulated D151801 with the 17140 ROM on the ECU board's pins (pins.h, car.h). The IGT and
# injector pins are held at their engine-stopped level: this build cannot run the engine.
cmake_minimum_required(VERSION 3.13)

set(PICO_PLATFORM rp2350)
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/pico_sdk_import.cmake)
project(ecu_emu_car C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

file(READ "${CMAKE_CURRENT_LIST_DIR}/../../../roms/mr2_17140/89661-17140.bin" ROM_HEX HEX)
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," ROM_ARRAY "${ROM_HEX}")
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/rom17140.h "static const unsigned char ROM17140[4096] = {${ROM_ARRAY}};\n")

add_executable(ecu_emu_car main.c ../core/hd6301.c ../core/d151801.c ../core/board.c)
pico_generate_pio_header(ecu_emu_car ${CMAKE_CURRENT_LIST_DIR}/car.pio)
target_include_directories(ecu_emu_car PRIVATE . ../core ${CMAKE_CURRENT_BINARY_DIR})
target_compile_options(ecu_emu_car PRIVATE -O2 -Wall -Wextra -Werror -Wno-unused-function)
target_link_libraries(ecu_emu_car pico_stdlib pico_multicore hardware_pio hardware_dma hardware_pwm)
pico_set_binary_type(ecu_emu_car copy_to_ram)
pico_enable_stdio_usb(ecu_emu_car 1)
pico_enable_stdio_uart(ecu_emu_car 0)
pico_add_extra_outputs(ecu_emu_car)
set_target_properties(ecu_emu_car PROPERTIES OUTPUT_NAME ecu_emu_car_${PICO_BOARD})
