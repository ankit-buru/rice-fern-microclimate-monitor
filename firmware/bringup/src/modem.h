// SIM7080G control (README "Modem power-on sequence", DESIGN.md §4.5) and its AT port on USART2.
#pragma once
#include <stdbool.h>
#include <stddef.h>

bool modem_rail_on(void);                 // PC13 (buck EN) driven high
bool modem_status(void);                  // PA4 STATUS: high = modem running
int  modem_power_on(void);                // rail on, 1.2 s PWRKEY pulse, wait STATUS: ms until STATUS, -1 = no STATUS
int  modem_power_off(void);               // AT+CPOWD=1, wait STATUS low, then rail off: ms, -1 = STATUS stayed high (rail left on)
void modem_kill(void);                    // rail off at once: hung-modem recovery only (can corrupt the modem's file system)
void modem_pwrkey_pulse(unsigned ms);     // raw PWRKEY press (Q1), for experiments
void modem_uart_attach(void);             // USART2 on PA2/PA3, 115200 8N1, no flow control
void modem_uart_detach(void);             // pins back to inputs (the safe modem-off state)
bool modem_uart_attached(void);
void modem_write(const char *s, size_t n);
int  modem_getc(void);                    // -1 if nothing received
int  modem_at(const char *cmd, unsigned timeout_ms, bool echo);   // send cmd + CR, print reply until OK/ERROR: 0 OK, 1 ERROR, -1 timeout
int  modem_query(const char *cmd, const char *prefix, char *out, size_t outlen, unsigned timeout_ms);  // first reply line starting with prefix
bool modem_sync(unsigned tries);          // "AT" until OK (the modem auto-bauds on the first ATs)
void modem_drain(unsigned ms);            // print whatever the modem says for ms (start-up messages, URCs)
int  modem_wait_line(const char *prefix, char *out, size_t outlen, unsigned timeout_ms);  // print lines until one starts with prefix: ms, -1 = timeout
size_t modem_read_raw(char *buf, size_t n, unsigned timeout_ms);   // exactly n bytes, or fewer on timeout
