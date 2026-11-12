// TreeWeather LTE board rev 0.9: STM32L072CBT6 pin map (hardware/lte_board/README.md "MCU pin map", schematic nets).
// Alternate-function numbers from DS10689 Tables 17/18.
#pragma once
#include "stm32l0xx.h"

typedef struct { GPIO_TypeDef *port; uint8_t pin; } pin_t;
#define PIN(p, n) ((pin_t){ GPIO##p, n })

// ---- modem (SIM7080G U6) through the TXS0108E level shifter U5 (OE = VDD_EXT: Hi-Z while the modem is off)
#define MDM_PWR_EN    PIN(C, 13)  // out: buck U2 EN through R28 (high = 3.8 V rail on); keep the RTC off PC13
#define MDM_PWRKEY    PIN(A, 7)   // out: Q1 base, high = PWRKEY pressed (pulled low)
#define MDM_STATUS    PIN(A, 4)   // in:  high = modem on (R27 100k pull-down)
#define MDM_TXD       PIN(A, 2)   // USART2_TX AF4 -> modem RXD
#define MDM_RXD       PIN(A, 3)   // USART2_RX AF4 <- modem TXD (R29 100k pull-up)
#define MDM_CTS       PIN(A, 0)   // USART2_CTS AF4 <- modem CTS (R31 100k pull-up)
#define MDM_RTS       PIN(A, 1)   // USART2_RTS AF4 -> modem RTS
#define MDM_DCD       PIN(A, 5)   // in (R30 100k pull-up)
#define MDM_DTR       PIN(H, 1)   // out
#define MDM_RI        PIN(H, 0)   // in, EXTI0 (R32 100k pull-down)
#define AF_USART2     4

// ---- GNSS antenna feed (U10 TPS22945)
#define GNSS_ANT_EN   PIN(B, 0)   // out: high = 3.3 V on the antenna (R39 pull-down = off)
#define GNSS_ANT_FLT  PIN(B, 1)   // in, needs the internal pull-up: low = antenna over-current

// ---- I2C buses
#define I2C1_SCL      PIN(B, 8)   // AF4  fuel gauge U8 (MAX17048, 0x36), R41/R42
#define I2C1_SDA      PIN(B, 7)   // AF1
#define I2C2_SCL      PIN(B, 13)  // AF5  Qwiic J3, R12/R13
#define I2C2_SDA      PIN(B, 11)  // AF6
#define I2C3_SCL      PIN(A, 8)   // AF7  Qwiic J11, R43/R44
#define I2C3_SDA      PIN(B, 4)   // AF7  (also J4 pin 6)
#define BAT_ALRT      PIN(B, 9)   // in, EXTI9: MAX17048 ALRT, open drain, R37 pull-up, low = alert
#define MAX17048_ADDR 0x36

// ---- user interface and misc
#define LED_USER      PIN(B, 15)  // out: D2 (high = on)
#define SIM_DET       PIN(B, 6)   // in: high = card present (R24 1M pull-up; the switch shorts to GND with no card)
#define DBG_TX        PIN(A, 9)   // USART1_TX AF4, J4 pin 5 (debug header, DNP)
#define DBG_RX        PIN(A, 10)  // USART1_RX AF4, J4 pin 3
// PA11/PA12 USB DM/DP (via JP4/JP3, default = MCU), PA13/PA14 SWD (J2), PC14/PC15 LSE crystal Y1 (32.768 kHz),
// J4 expansion: PA15, PB3, PB4 (= I2C3_SDA), PB5.  Spare: PA6, PB2, PB10, PB12, PB14.
