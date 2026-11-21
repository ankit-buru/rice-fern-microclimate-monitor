#include <stdarg.h>
#include <stdio.h>
#include "console.h"
#include "hw.h"
#include "tusb.h"

void console_init(void) {
  RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
  pin_pull(DBG_RX, PULL_UP);                                   // J4 is usually not fitted: keep RX from floating
  pin_af(DBG_TX, 4); pin_af(DBG_RX, 4);
  USART1->BRR = 16000000u / 115200u;
  USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

bool console_usb_connected(void) { return tud_cdc_connected(); }

static void usb_write(const char *buf, size_t n) {
  if (!tud_cdc_connected()) return;                            // nobody listening: don't stall
  uint32_t t0 = millis();
  while (n) {
    uint32_t k = tud_cdc_write(buf, n);
    buf += k; n -= k;
    if (n) {
      tud_cdc_write_flush(); tud_task();
      if (millis() - t0 > 200) return;                         // host stopped reading
    }
  }
  tud_cdc_write_flush();
}

static void uart_write(const char *buf, size_t n) {
  while (n--) { while (!(USART1->ISR & USART_ISR_TXE)) {} USART1->TDR = (uint8_t)*buf++; }
}

void cwrite_raw(const char *buf, size_t n) { usb_write(buf, n); uart_write(buf, n); }

void cputs(const char *s) {
  const char *start = s;
  for (; *s; s++)
    if (*s == '\n') { cwrite_raw(start, s - start); cwrite_raw("\r\n", 2); start = s + 1; }
  cwrite_raw(start, s - start);
}

void cprintf(const char *fmt, ...) {
  char buf[256];
  va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  cputs(buf);
}

int console_getc(void) {
  if (tud_cdc_available()) return tud_cdc_read_char();
  if (USART1->ISR & USART_ISR_ORE) USART1->ICR = USART_ICR_ORECF;
  if (USART1->ISR & USART_ISR_RXNE) return (int)(USART1->RDR & 0xFF);
  return -1;
}

const char *console_readline(void) {
  static char line[96];
  static unsigned n;
  int c;
  while ((c = console_getc()) >= 0) {
    if (c == '\r' || c == '\n') {
      if (c == '\n' && n == 0) continue;                       // the LF of a CR LF
      cputs("\n"); line[n] = 0; n = 0; return line;
    }
    if ((c == 8 || c == 127) && n) { n--; cputs("\b \b"); continue; }
    if (c >= ' ' && c < 127 && n < sizeof line - 1) { line[n++] = (char)c; char e[2] = { (char)c, 0 }; cputs(e); }
  }
  return NULL;
}

// Stop mode and USB: just dropping the D+ pull-up (tud_disconnect) left the peripheral in its suspend state with its
// clock stopped, and the second reconnect after a sleep wasn't seen by the host. So shut it all down and start afresh.
void console_usb_stop(void) {
  if (!tud_inited()) return;
  tud_deinit(0);                                                // interrupts off, D+ pull-up off, core powered down
  NVIC_ClearPendingIRQ(USB_IRQn);
  RCC->APB1ENR &= ~(RCC_APB1ENR_USBEN | RCC_APB1ENR_CRSEN);
}

void console_usb_start(void) {
  if (tud_inited()) return;
  hw_usb_clock_resume();                                        // HSI48 (stopped in Stop mode)
  RCC->APB1RSTR |= RCC_APB1RSTR_USBRST | RCC_APB1RSTR_CRSRST;   // clean peripherals
  RCC->APB1RSTR &= ~(RCC_APB1RSTR_USBRST | RCC_APB1RSTR_CRSRST);
  RCC->APB1ENR |= RCC_APB1ENR_CRSEN | RCC_APB1ENR_USBEN;
  CRS->CR |= CRS_CR_AUTOTRIMEN | CRS_CR_CEN;
  tusb_rhport_init_t init = { .role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_AUTO };
  tusb_init(0, &init);                                          // pull-up on: the host sees a new attach
}
