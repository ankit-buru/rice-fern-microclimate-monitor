// Settings kept in the STM32's data EEPROM (survive power-off and reflashing): where to report, and how often.
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
  uint32_t magic;          // CONFIG_MAGIC when valid
  uint32_t interval_s;     // seconds between reports in field mode
  char     url[64];        // http://host:port (SHCONF "URL": scheme + host + port, max 64 bytes, manual §13.2.1)
  char     token[32];      // sent as the X-Token header; empty = none
} config_t;

extern config_t cfg;
void config_load(void);    // defaults if the EEPROM is blank or from an older layout
bool config_save(void);    // false if the read-back doesn't match
