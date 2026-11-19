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
    cfg.interval_s = 300;
  }
  cfg.url[sizeof cfg.url - 1] = 0; cfg.token[sizeof cfg.token - 1] = 0;
  if (cfg.interval_s < 60) cfg.interval_s = 60;
}

// Data EEPROM word writes: unlock PECR with the two PEKEYR keys, store the word (the hardware erases and programs
// it), wait for BSY to clear, lock again. The key values are ST's FLASH_PEKEY1/2 as remembered (RM0376 is not
// local): the read-back below catches a mistake.
bool config_save(void) {
  const uint32_t *src = (const uint32_t *)&cfg;
  volatile uint32_t *dst = (volatile uint32_t *)CONFIG_ADDR;
  while (FLASH->SR & FLASH_SR_BSY) {}
  if (FLASH->PECR & FLASH_PECR_PELOCK) { FLASH->PEKEYR = 0x89ABCDEFu; FLASH->PEKEYR = 0x02030405u; }
  for (unsigned i = 0; i < sizeof cfg / 4; i++) {
    if (dst[i] == src[i]) continue;
    dst[i] = src[i];
    while (FLASH->SR & FLASH_SR_BSY) {}
    FLASH->SR = FLASH_SR_EOP;
  }
  FLASH->PECR |= FLASH_PECR_PELOCK;
  return memcmp((const void *)CONFIG_ADDR, &cfg, sizeof cfg) == 0;
}
