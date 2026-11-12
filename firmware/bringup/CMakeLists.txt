# TreeWeather board bring-up firmware (STM32L072CBT6). Build:
#   ./fetch_deps.sh
#   cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake && cmake --build build
#   cmake --build build --target flash        (board in ROM DFU: hold BOOT0, tap RESET; or type "dfu" in the console)
cmake_minimum_required(VERSION 3.20)
set(CMAKE_TOOLCHAIN_FILE ${CMAKE_CURRENT_LIST_DIR}/cmake/arm-none-eabi.cmake CACHE FILEPATH "")
project(bringup C ASM)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)      # build/compile_commands.json for clangd / editors
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE MinSizeRel)
endif()

set(TP ${CMAKE_CURRENT_LIST_DIR}/third_party)
if(NOT EXISTS ${TP}/tinyusb/src/tusb.c)
  message(FATAL_ERROR "third_party/ is missing: run ./fetch_deps.sh first")
endif()
set(TUSB ${TP}/tinyusb/src)

add_executable(bringup
  src/main.c
  src/hw.c
  src/console.c
  src/i2c.c
  src/modem.c
  src/usb_descriptors.c
  src/syscalls.c
  ${TP}/cmsis-device-l0/Source/Templates/gcc/startup_stm32l072xx.s
  ${TP}/cmsis-device-l0/Source/Templates/system_stm32l0xx.c
  ${TUSB}/tusb.c
  ${TUSB}/common/tusb_fifo.c
  ${TUSB}/device/usbd.c
  ${TUSB}/class/cdc/cdc_device.c
  ${TUSB}/portable/st/stm32_fsdev/dcd_stm32_fsdev.c
  ${TUSB}/portable/st/stm32_fsdev/fsdev_common.c
)
set_target_properties(bringup PROPERTIES SUFFIX ".elf")
target_include_directories(bringup PRIVATE
  src
  ${TP}/cmsis-device-l0/Include
  ${TP}/CMSIS_5/CMSIS/Core/Include
  ${TUSB}
)
target_compile_definitions(bringup PRIVATE STM32L072xx CFG_TUSB_MCU=OPT_MCU_STM32L0)
target_compile_options(bringup PRIVATE $<$<COMPILE_LANGUAGE:C>:-std=gnu11 -Wall -Wextra -Wno-unused-parameter>)
# third-party sources: no warnings from code we don't own
set_source_files_properties(
  ${TP}/cmsis-device-l0/Source/Templates/system_stm32l0xx.c ${TUSB}/tusb.c ${TUSB}/common/tusb_fifo.c ${TUSB}/device/usbd.c
  ${TUSB}/class/cdc/cdc_device.c ${TUSB}/portable/st/stm32_fsdev/dcd_stm32_fsdev.c ${TUSB}/portable/st/stm32_fsdev/fsdev_common.c
  PROPERTIES COMPILE_OPTIONS "-w")
target_link_options(bringup PRIVATE -T${CMAKE_CURRENT_LIST_DIR}/STM32L072CB.ld -Wl,-Map=$<TARGET_FILE_DIR:bringup>/bringup.map -Wl,--no-warn-rwx-segments)

add_custom_command(TARGET bringup POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:bringup> ${CMAKE_BINARY_DIR}/bringup.bin
  COMMAND ${CMAKE_SIZE} $<TARGET_FILE:bringup>
  COMMENT "bringup.bin, size (128 KB flash, 20 KB RAM)")

# ST ROM DFU (AN2606): alt setting 0 = internal flash; ":leave" starts the new firmware when the download is done
add_custom_target(flash
  COMMAND dfu-util -a 0 -d 0483:df11 -s 0x08000000:leave -D ${CMAKE_BINARY_DIR}/bringup.bin
  DEPENDS bringup
  COMMENT "Flashing over USB DFU (board must be in the ST bootloader)")
