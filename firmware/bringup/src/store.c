#include <string.h>
#include "config.h"
#include "hw.h"
#include "store.h"

// Data EEPROM map (6 KB, 0x08080000-0x080817FF):  0x000 settings (config_t, <= 128 B) | 0x080 header | 0x100 records
#define HDR_ADDR    (DATA_EEPROM_BASE + 0x80u)
#define REC_ADDR    (DATA_EEPROM_BASE + 0x100u)
#define STORE_CAP   ((DATA_EEPROM_BANK2_END + 1u - REC_ADDR) / sizeof(rec_t))   // 294 records: ~3 days at 15 min
#define STORE_MAGIC (0x53540000u | (sizeof(rec_t) << 8) | 1u)   // "ST", record size, layout 1

_Static_assert(sizeof(rec_t) == 20, "rec_t layout");
_Static_assert(sizeof(config_t) <= 0x80, "config_t would overlap the store header");

typedef struct { uint32_t magic, acked, epoch, spare; } hdr_t;   // acked: rewritten once per upload (100k cycles: decades)

static hdr_t hdr;
static uint32_t newest;

static uint8_t crc8(const uint8_t *p, unsigned n) {          // CRC-8, polynomial 0x07
  uint8_t c = 0;
  while (n--) { c ^= *p++; for (int i = 0; i < 8; i++) c = (uint8_t)(c & 0x80 ? (c << 1) ^ 0x07 : c << 1); }
  return c;
}

static uint32_t slot_addr(uint32_t seq) { return REC_ADDR + ((seq - 1u) % STORE_CAP) * sizeof(rec_t); }

static bool slot_valid(const rec_t *r) { return r->seq && r->crc == crc8((const uint8_t *)r, sizeof *r - 1); }

unsigned store_capacity(void) { return STORE_CAP; }
uint32_t store_newest(void) { return newest; }
uint32_t store_acked(void) { return hdr.acked; }
uint32_t store_epoch(void) { return hdr.epoch; }

void store_clear(void) {
  uint32_t zero = 0;
  for (uint32_t i = 0; i < STORE_CAP; i++) {                  // seq = 0 marks a slot empty (~1 s for all of them)
    uint32_t a = REC_ADDR + i * sizeof(rec_t);
    if (*(volatile uint32_t *)a) hw_eeprom_write(a, &zero, 4);
  }
  hdr_t old; memcpy(&old, (const void *)HDR_ADDR, sizeof old);
  hdr.magic = STORE_MAGIC; hdr.acked = 0; hdr.spare = 0;
  hdr.epoch = (old.magic == STORE_MAGIC ? old.epoch : hw_clock_s()) + 1u;
  hw_eeprom_write(HDR_ADDR, &hdr, sizeof hdr);
  newest = 0;
}

void store_init(void) {
  memcpy(&hdr, (const void *)HDR_ADDR, sizeof hdr);
  if (hdr.magic != STORE_MAGIC) { store_clear(); return; }
  newest = 0;
  for (uint32_t i = 0; i < STORE_CAP; i++) {
    rec_t r; memcpy(&r, (const void *)(REC_ADDR + i * sizeof r), sizeof r);
    if (slot_valid(&r) && (r.seq - 1u) % STORE_CAP == i && r.seq > newest) newest = r.seq;
  }
  if (hdr.acked > newest) hdr.acked = newest;                 // can't have acked what isn't there
}

uint32_t store_append(rec_t *r) {
  r->seq = newest + 1u;
  r->crc = crc8((const uint8_t *)r, sizeof *r - 1);
  if (!hw_eeprom_write(slot_addr(r->seq), r, sizeof *r)) return 0;
  return newest = r->seq;
}

bool store_get(uint32_t seq, rec_t *r) {
  if (!seq || seq > newest || newest - seq >= STORE_CAP) return false;
  memcpy(r, (const void *)slot_addr(seq), sizeof *r);
  return slot_valid(r) && r->seq == seq;
}

uint32_t store_first_unsent(void) {
  uint32_t first = hdr.acked + 1u;
  if (newest >= STORE_CAP && first < newest - STORE_CAP + 1u) first = newest - STORE_CAP + 1u;   // overwritten
  return first;
}

uint32_t store_unsent(void) { return newest + 1u - store_first_unsent(); }

void store_ack(uint32_t seq) {
  if (seq > newest) seq = newest;
  if (seq <= hdr.acked) return;
  hdr.acked = seq;
  hw_eeprom_write(HDR_ADDR, &hdr, sizeof hdr);
}
