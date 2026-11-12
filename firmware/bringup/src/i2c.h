// I2C1 (fuel gauge), I2C2 (Qwiic J3), I2C3 (Qwiic J11): 100 kHz masters, polled.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { I2C_OK = 0, I2C_NACK = -1, I2C_TIMEOUT = -2 };

const char *i2c_name(int bus);                                  // bus = 1, 2, 3
void i2c_lines(int bus, bool *scl, bool *sda);                  // idle levels with the peripheral off (both 1 = pull-ups OK)
bool i2c_recover(int bus);                                      // 9 SCL clocks to free a device holding SDA low
void i2c_init(int bus);
int  i2c_xfer(int bus, uint8_t addr, const uint8_t *w, size_t wn, uint8_t *r, size_t rn);
bool i2c_probe(int bus, uint8_t addr);                          // address ACKs
int  i2c_read_reg16(int bus, uint8_t addr, uint8_t reg, uint16_t *v);   // big-endian 16-bit register
