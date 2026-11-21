// Low-level hardware: clocks, millisecond tick, GPIO helpers, reset cause, ROM bootloader, VDDA, LSE + RTC.
#pragma once
#include <stdbool.h>
#include <stddef.h>
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

// ---- independent watchdog (LSI, DS10689 Table 49: 26-56 kHz): /256 and reload 4095 = 19-40 s without a kick.
// Started for unattended operation only: once running it can't be stopped, except by a reset.
void hw_watchdog_start(void);
void hw_watchdog_kick(void);
bool hw_watchdog_running(void);

// ---- device clock: the RTC on the LSE (LSI if Y1 won't start), counting seconds from its first start. It keeps
// running through resets and reflashing (backup domain); a power cut (cell disconnected) restarts it from 0.
bool hw_clock_init(void);       // idempotent; true = on the LSE
bool hw_clock_fresh(void);      // the clock (re)started from 0 at this boot
uint32_t hw_clock_s(void);      // device seconds
uint32_t hw_clock_read(uint32_t *ms);   // device seconds, and ms into the current second
uint32_t hw_bkp_read(unsigned i);       // RTC backup registers 0..4: survive resets, like the clock
void hw_bkp_write(unsigned i, uint32_t v);

// ---- Stop mode between field-mode events (~1 uA for the MCU: DS10689 Table 37 + RTC/LSE/IWDG, Table 41)
void hw_stop_ms(uint32_t ms);   // Stop mode for ms (<= 30 s), floating inputs parked as analog; millis() advanced
void hw_usb_clock_resume(void); // HSI48 back on after Stop

// ---- analog: VDDA (the +3V3 rail) from the internal reference; the MCU's own temperature sensor
unsigned hw_vdda_mv(void);
int hw_mcu_temp_dc(void);       // 0.1 C (DS10689 Table 69: +-2 C linearity after the two-point cal); -9999 = no cal

// ---- data EEPROM: word-aligned writes, unchanged words skipped; false if the read-back doesn't match
bool hw_eeprom_write(uint32_t addr, const void *src, size_t n);

// ---- LSE crystal Y1
int  hw_lse_start(unsigned drive, uint32_t timeout_ms);   // drive 0 (low) .. 3 (high); returns start time in ms, -1 = failed
bool hw_lse_ready(void);
