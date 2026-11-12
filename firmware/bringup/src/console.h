// Console on the USB CDC port, mirrored to USART1 (J4 pins 3/5, 115200 8N1) for when USB itself is the problem.
#pragma once
#include <stdbool.h>
#include <stddef.h>

void console_init(void);
void cputs(const char *s);                                     // "\n" goes out as "\r\n"
void cprintf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void cwrite_raw(const char *buf, size_t n);                    // no newline translation (modem bridge)
int  console_getc(void);                                       // -1 if nothing waiting
const char *console_readline(void);                            // non-blocking: a finished line, or NULL
bool console_usb_connected(void);                              // a terminal has the CDC port open (DTR set)
