#include <string.h>
#include "modem.h"
#include "console.h"
#include "hw.h"

// ---------------------------------------------------------------- USART2 receive ring (interrupt driven)
static volatile uint8_t rx[1024];
static volatile unsigned rx_head, rx_tail;
static bool attached;

void USART2_IRQHandler(void) {
  uint32_t isr = USART2->ISR;
  if (isr & USART_ISR_ORE) USART2->ICR = USART_ICR_ORECF;
  if (isr & USART_ISR_RXNE) {
    uint8_t c = (uint8_t)USART2->RDR;
    unsigned h = (rx_head + 1) % sizeof rx;
    if (h != rx_tail) { rx[rx_head] = c; rx_head = h; }          // full: drop
  }
}

int modem_getc(void) {
  if (rx_tail == rx_head) return -1;
  int c = rx[rx_tail]; rx_tail = (rx_tail + 1) % sizeof rx;
  return c;
}

bool modem_uart_attached(void) { return attached; }

void modem_uart_attach(void) {
  if (attached) return;
  RCC->APB1ENR |= RCC_APB1ENR_USART2EN;
  pin_af(MDM_TXD, AF_USART2); pin_af(MDM_RXD, AF_USART2);       // RXD has R29 100k pull-up: no internal pull
  USART2->CR1 = 0;
  USART2->BRR = 16000000u / 115200u;
  USART2->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_RXNEIE | USART_CR1_UE;
  rx_head = rx_tail = 0;
  NVIC_EnableIRQ(USART2_IRQn);
  attached = true;
}

void modem_uart_detach(void) {
  NVIC_DisableIRQ(USART2_IRQn);
  USART2->CR1 = 0;
  pin_mode(MDM_TXD, MODE_IN); pin_mode(MDM_RXD, MODE_IN);       // DESIGN.md §8: inputs, no pulls, while the modem is off
  attached = false;
}

void modem_write(const char *s, size_t n) {
  if (!attached) return;
  while (n--) { while (!(USART2->ISR & USART_ISR_TXE)) {} USART2->TDR = (uint8_t)*s++; }
}

// ---------------------------------------------------------------- power
bool modem_rail_on(void) { return pin_out_level(MDM_PWR_EN); }
bool modem_status(void) { return pin_read(MDM_STATUS); }

void modem_pwrkey_pulse(unsigned ms) {
  pin_write(MDM_PWRKEY, 1);                                       // Q1 on: PWRKEY pulled low
  delay_ms(ms);
  pin_write(MDM_PWRKEY, 0);
}

static int wait_status(bool level, unsigned timeout_ms) {
  uint32_t t0 = millis();
  while (modem_status() != level) {
    if (millis() - t0 > timeout_ms) return -1;
    system_poll();
  }
  return (int)(millis() - t0);
}

int modem_power_on(void) {
  if (modem_status()) { modem_uart_attach(); return 0; }          // already running
  pin_write(MDM_PWR_EN, 1);                                       // 1. buck on
  delay_ms(50);
  uint32_t t0 = millis();
  modem_pwrkey_pulse(1200);                                       // 2. PWRKEY low >= 1 s
  if (wait_status(1, 8000) < 0) return -1;                        // 3. STATUS high (>= 1.8 s after the press)
  int ms = (int)(millis() - t0);
  modem_uart_attach();
  return ms;
}

int modem_power_off(void) {
  if (!modem_rail_on() && !modem_status()) return 0;
  uint32_t t0 = millis();
  if (modem_status()) {
    modem_uart_attach();
    modem_at("AT+CPOWD=1", 2000, true);                           // 4. graceful power down
    if (wait_status(0, 15000) < 0) return -1;                     // still running: don't cut the rail
  }
  modem_uart_detach();
  delay_ms(100);
  pin_write(MDM_PWR_EN, 0);                                       //    then the rail
  return (int)(millis() - t0);
}

void modem_kill(void) {
  modem_uart_detach();
  pin_write(MDM_PWRKEY, 0);
  pin_write(MDM_PWR_EN, 0);
}

// ---------------------------------------------------------------- AT helper
// Final result codes per the SIM7070/7080/7090 AT Command Manual V1.05: OK, ERROR, +CME/+CMS ERROR, and
// "NORMAL POWER DOWN", which is AT+CPOWD=1's only reply (§5.2.1).
static char capture_prefix[16], *capture_buf;
static size_t capture_len;

int modem_query(const char *cmd, const char *prefix, char *out, size_t outlen, unsigned timeout_ms) {
  strncpy(capture_prefix, prefix, sizeof capture_prefix - 1); capture_prefix[sizeof capture_prefix - 1] = 0;
  capture_buf = out; capture_len = outlen; out[0] = 0;
  int rc = modem_at(cmd, timeout_ms, false);
  capture_buf = NULL;
  return rc;
}

int modem_at(const char *cmd, unsigned timeout_ms, bool echo) {
  char line[160];
  unsigned n = 0;
  while (modem_getc() >= 0) {}                                    // drop stale bytes
  modem_write(cmd, strlen(cmd)); modem_write("\r", 1);
  uint32_t t0 = millis();
  while (millis() - t0 < timeout_ms) {
    system_poll();
    int c;
    while ((c = modem_getc()) >= 0) {
      if (c == '\r') continue;
      if (c != '\n' && n < sizeof line - 1) { line[n++] = (char)c; continue; }
      if (c != '\n') continue;
      line[n] = 0;
      if (n && echo && strcmp(line, "OK")) cprintf("  < %s\n", line);
      if (capture_buf && !capture_buf[0] && !strncmp(line, capture_prefix, strlen(capture_prefix))) {
        strncpy(capture_buf, line, capture_len - 1); capture_buf[capture_len - 1] = 0;
      }
      if (!strcmp(line, "OK") || !strcmp(line, "NORMAL POWER DOWN")) return 0;
      if (!strcmp(line, "ERROR") || !strncmp(line, "+CME ERROR", 10) || !strncmp(line, "+CMS ERROR", 10)) return 1;
      n = 0;
    }
  }
  if (n && echo) { line[n] = 0; cprintf("  < %s (no newline)\n", line); }
  return -1;
}

void modem_drain(unsigned ms) {
  char line[160];
  unsigned n = 0;
  uint32_t t0 = millis();
  while (millis() - t0 < ms) {
    system_poll();
    int c;
    while ((c = modem_getc()) >= 0) {
      if (c == '\r') continue;
      if (c != '\n') { if (n < sizeof line - 1) line[n++] = (char)c; continue; }
      line[n] = 0;
      if (n) cprintf("  < %s\n", line);
      n = 0;
    }
  }
}

int modem_wait_line(const char *prefix, char *out, size_t outlen, unsigned timeout_ms) {
  char line[160];
  unsigned n = 0;
  uint32_t t0 = millis();
  while (millis() - t0 < timeout_ms) {
    system_poll();
    int c;
    while ((c = modem_getc()) >= 0) {
      if (c == '\r') continue;
      if (c != '\n') { if (n < sizeof line - 1) line[n++] = (char)c; continue; }
      line[n] = 0; n = 0;
      if (!line[0]) continue;
      cprintf("  < %s\n", line);
      if (!strncmp(line, prefix, strlen(prefix))) {
        if (out) { strncpy(out, line, outlen - 1); out[outlen - 1] = 0; }
        return (int)(millis() - t0);
      }
    }
  }
  return -1;
}

bool modem_sync(unsigned tries) {
  for (unsigned i = 0; i < tries; i++)
    if (modem_at("AT", 500, false) == 0) return true;
  return false;
}
