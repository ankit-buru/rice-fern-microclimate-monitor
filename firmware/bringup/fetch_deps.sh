#!/bin/sh
# Fetch the pinned third-party code into third_party/ (not committed; see .gitignore).
#   cmsis-device-l0  ST's STM32L0 register headers, startup file and system_stm32l0xx.c   (Apache-2.0)
#   CMSIS_5          Arm's Cortex-M core headers (CMSIS/Core/Include)                     (Apache-2.0)
#   tinyusb          USB device stack, used for the CDC serial console                    (MIT)
set -e
cd "$(dirname "$0")"
mkdir -p third_party
get() {   # repo tag dir
    if [ -d "third_party/$3" ]; then echo "third_party/$3 already present"; return; fi
    git -c advice.detachedHead=false clone --depth 1 --branch "$2" "https://github.com/$1.git" "third_party/$3"
}
get STMicroelectronics/cmsis-device-l0 v1.9.4 cmsis-device-l0
get ARM-software/CMSIS_5              5.9.0  CMSIS_5
get hathach/tinyusb                   0.21.0 tinyusb
