// Settings kept (layout 1, fields only ever appended; at most 128 bytes: the sample store follows) in the STM32's data EEPROM (survive power-off and reflashing): where to report, how often to sample and upload.
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
  uint32_t magic;          // CONFIG_MAGIC when valid
  uint32_t unused;         // was interval_s (one report per interval, before sampling and batches)
  char     url[64];        // http://host:port (SHCONF "URL": scheme + host + port, max 64 bytes, manual §13.2.1)
  char     token[32];      // sent as the X-Token header; empty = none
  uint32_t sample_s;       // seconds between samples (default 900)
  uint32_t batch;          // upload once this many samples are waiting (default 4: hourly at 900 s)
  char     name[16];       // label set by the user (cfg name), sent with every upload; the server's key stays the
                           // MCU's unique ID. Letters, digits, - and _ only (no JSON escaping needed). Empty = none.
} config_t;

extern config_t cfg;
void config_load(void);    // defaults if the EEPROM is blank or from an older layout
bool config_save(void);    // false if the read-back doesn't match
