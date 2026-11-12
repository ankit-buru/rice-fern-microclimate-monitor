// Low-level hardware: clocks, millisecond tick, GPIO helpers, reset cause, ROM bootloader, VDDA, LSE + RTC.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "board.h"

// ---- GPIO (MODER: 0 input, 1 output, 2 alternate function, 3 analog; PUPDR: 0 none, 1 up, 2 down)
enum { MODE_IN = 0, MODE_OUT = 1, MODE_AF = 2, MODE_ANALOG = 3 };
enum { PULL_NONE = 0, PULL_UP = 1, PULL_DOWN = 2 };

static inline void pin_mode(pin_t p, unsigned mode) {
  p.port->MODER = (p.port->MODER & ~(3u << (2 * p.pin))) | (mode << (2 * p.pin));
}
static inline void pin_pull(pin_t p, unsigned pull) {
  p.port->PUPDR = (p.port->PUPDR & ~(3u << (2 * p.pin))) | (pull << (2 * p.pin));
}
static inline void pin_open_drain(pin_t p, bool od) {
  if (od) p.port->OTYPER |= 1u << p.pin; else p.port->OTYPER &= ~(1u << p.pin);
}
static inline void pin_af(pin_t p, unsigned af) {
  volatile uint32_t *r = &p.port->AFR[p.pin >> 3];
  *r = (*r & ~(0xFu << (4 * (p.pin & 7)))) | (af << (4 * (p.pin & 7)));
  pin_mode(p, MODE_AF);
}
static inline void pin_write(pin_t p, bool v) { p.port->BSRR = v ? (1u << p.pin) : (1u << (p.pin + 16)); }
static inline bool pin_read(pin_t p) { return (p.port->IDR >> p.pin) & 1u; }
static inline bool pin_out_level(pin_t p) { return (p.port->ODR >> p.pin) & 1u; }
static inline void pin_output(pin_t p, bool v) { pin_write(p, v); pin_mode(p, MODE_OUT); }   // level first: no glitch

// ---- clocks and time
void hw_early(void);            // first thing in main(): jumps to the ROM bootloader if "dfu" asked for it
void hw_init(void);             // clocks (HSI16 core, HSI48 + CRS for USB), SysTick, safe pin states
uint32_t millis(void);
void delay_ms(uint32_t ms);     // keeps calling system_poll() so USB stays alive
void system_poll(void);         // provided by main.c: USB task and modem UART service

// ---- identity, reset, bootloader
uint32_t hw_reset_flags(void);  // RCC_CSR reset flags captured at boot
const char *hw_reset_cause(void);
void hw_uid(uint32_t uid[3]);
unsigned hw_flash_kb(void);
void hw_enter_bootloader(void); // reboot into the ST ROM DFU bootloader (as BOOT0 + RESET would)

// ---- analog: VDDA (the +3V3 rail) from the internal reference
unsigned hw_vdda_mv(void);

// ---- LSE crystal Y1 and RTC
int  hw_lse_start(unsigned drive, uint32_t timeout_ms);   // drive 0 (low) .. 3 (high); returns start time in ms, -1 = failed
bool hw_lse_ready(void);
void hw_rtc_start(void);        // RTC on the LSE, time reset to 00:00:00
uint32_t hw_rtc_seconds(void);  // seconds since hw_rtc_start (wraps at 24 h)
