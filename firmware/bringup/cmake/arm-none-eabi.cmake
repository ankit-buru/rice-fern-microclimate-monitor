# CMake toolchain file: Arm GNU Toolchain (arm-none-eabi-gcc) on the PATH, Cortex-M0+ (STM32L072).
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)   # no host-runnable test programs

find_program(ARM_GCC arm-none-eabi-gcc REQUIRED
             DOC "Arm GNU Toolchain; see firmware/bringup/README.md for install instructions")
get_filename_component(ARM_BIN ${ARM_GCC} DIRECTORY)
set(CMAKE_C_COMPILER   ${ARM_BIN}/arm-none-eabi-gcc)
set(CMAKE_ASM_COMPILER ${ARM_BIN}/arm-none-eabi-gcc)
set(CMAKE_OBJCOPY      ${ARM_BIN}/arm-none-eabi-objcopy CACHE FILEPATH "")
set(CMAKE_SIZE         ${ARM_BIN}/arm-none-eabi-size CACHE FILEPATH "")

set(CPU_FLAGS "-mcpu=cortex-m0plus -mthumb")
set(CMAKE_C_FLAGS_INIT   "${CPU_FLAGS} -ffunction-sections -fdata-sections -fno-common")
set(CMAKE_ASM_FLAGS_INIT "${CPU_FLAGS} -x assembler-with-cpp")
set(CMAKE_EXE_LINKER_FLAGS_INIT "${CPU_FLAGS} -Wl,--gc-sections --specs=nano.specs --specs=nosys.specs")
