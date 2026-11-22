// Sample records kept in the data EEPROM until the server confirms it has them (DESIGN.md §8, F04).
// A ring of fixed 44-byte slots after the settings; record <seq> always lives in slot (seq - 1) % STORE_CAP, so the
// newest record is found by scanning once at boot and nothing else needs a write per sample. When the ring is full
// the oldest record is overwritten (the server sees the gap in the numbers).
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "sensors.h"

typedef struct {
  uint32_t seq;                    // 1, 2, 3 ... (0 = empty slot)
  uint32_t t;                      // device clock (hw_clock_s) when sampled
  uint16_t vcell_mv;               // cell voltage, 0 = no fuel gauge
  int16_t  mcu_dc;                 // MCU temperature, 0.1 C
  sensors_t s;                     // Qwiic sensors, raw (sensors.h); s.status says which answered
  uint8_t  flags;                  // REC_*
  uint8_t  pad[2];
  uint8_t  crc;                    // CRC-8 of the bytes before it: a record cut short by a reset reads as empty
} rec_t;

enum {
  REC_BOOT       = 0x01,           // first sample since an MCU reset
  REC_CLOCK_NEW  = 0x02,           // ... and the device clock restarted from 0 (power was cut)
  REC_BATT_LOW   = 0x04,           // cell below BATT_LOW_MV
  REC_LOCKED_OUT = 0x08,           // uploads stopped for a low cell
  REC_USB        = 0x10,           // a USB host was connected
};

void     store_init(void);         // find the newest record; wipe the area if its layout changed
uint32_t store_append(rec_t *r);   // fills seq + crc, writes the slot; returns seq (0 = EEPROM write failed)
bool     store_get(uint32_t seq, rec_t *r);   // false = never written, overwritten, or corrupt
uint32_t store_newest(void);       // 0 = none yet
uint32_t store_acked(void);        // the server has everything up to here
uint32_t store_first_unsent(void); // oldest record still worth sending (store_newest() + 1 = none)
uint32_t store_unsent(void);
void     store_ack(uint32_t seq);  // the server confirmed everything up to seq
uint32_t store_epoch(void);        // changes on every wipe: (epoch, seq) is unique for this board
unsigned store_capacity(void);
void     store_clear(void);
