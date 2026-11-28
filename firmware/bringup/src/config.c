#include <string.h>
#include "config.h"
#include "hw.h"

#define CONFIG_MAGIC 0x54570001u                               // "TW", layout 1
#define CONFIG_ADDR  DATA_EEPROM_BASE                          // bank 1 of the 6 KB data EEPROM

config_t cfg;

void config_load(void) {
  memcpy(&cfg, (const void *)CONFIG_ADDR, sizeof cfg);
  if (cfg.magic != CONFIG_MAGIC) {
    memset(&cfg, 0, sizeof cfg);
    cfg.magic = CONFIG_MAGIC;
  }
  if (!cfg.sample_s) cfg.sample_s = 900;                        // fields added after layout 1 read as 0 on older boards
  if (!cfg.batch) cfg.batch = 4;
  cfg.url[sizeof cfg.url - 1] = 0; cfg.token[sizeof cfg.token - 1] = 0; cfg.name[sizeof cfg.name - 1] = 0;
  if (cfg.sample_s < 60) cfg.sample_s = 60;
  if (cfg.batch > 96) cfg.batch = 96;
}

bool config_save(void) { return hw_eeprom_write(CONFIG_ADDR, &cfg, sizeof cfg); }
