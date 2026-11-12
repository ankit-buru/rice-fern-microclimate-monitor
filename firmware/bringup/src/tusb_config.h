// TinyUSB configuration: one CDC-ACM serial port (the bring-up console), full speed, no RTOS.
#pragma once

#ifndef CFG_TUSB_MCU
#error CFG_TUSB_MCU must be defined (OPT_MCU_STM32L0, set by CMakeLists.txt)
#endif
#define CFG_TUSB_OS               OPT_OS_NONE
#define CFG_TUSB_DEBUG            0
#define CFG_TUD_ENABLED           1
#define CFG_TUD_MAX_SPEED         OPT_MODE_FULL_SPEED
#define CFG_TUSB_MEM_ALIGN        __attribute__((aligned(4)))
#define CFG_TUD_ENDPOINT0_SIZE    64

#define CFG_TUD_CDC               1
#define CFG_TUD_MSC               0
#define CFG_TUD_HID               0
#define CFG_TUD_MIDI              0
#define CFG_TUD_VENDOR            0
#define CFG_TUD_CDC_NOTIFY        1
#define CFG_TUD_CDC_RX_BUFSIZE    128
#define CFG_TUD_CDC_TX_BUFSIZE    512   // room for a screen of output between USB polls
#define CFG_TUD_CDC_EP_BUFSIZE    64
