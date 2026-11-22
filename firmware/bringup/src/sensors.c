#include <string.h>
#include "console.h"
#include "hw.h"
#include "i2c.h"
#include "sensors.h"

#define AHT_ADDR  0x38
#define VEML_ADDR 0x10
#define AS_ADDR   0x74

static int aht_bus, veml_bus, as_bus;                          // 2 or 3; 0 = not found
static bool aht_ready, as_ready;

static int find(uint8_t addr) {
  for (int b = 2; b <= 3; b++) { i2c_init(b); if (i2c_probe(b, addr)) return b; }
  return 0;
}

static int wr(int bus, uint8_t addr, const uint8_t *w, int n) { return i2c_xfer(bus, addr, w, (size_t)n, NULL, 0); }

// ---------------------------------------------------------------- AHT20 (Adafruit_AHTX0)
static int aht_status(void) {
  uint8_t s;
  return i2c_xfer(aht_bus, AHT_ADDR, NULL, 0, &s, 1) == I2C_OK ? s : -1;
}

static bool aht_wait_idle(uint32_t ms) {                       // busy = status bit 7
  uint32_t t0 = millis();
  for (;;) {
    int s = aht_status();
    if (s >= 0 && !(s & 0x80)) return true;
    if (millis() - t0 > ms) return false;
    delay_ms(10);
  }
}

static bool aht_init(void) {
  static const uint8_t reset = 0xBA, cal[3] = { 0xE1, 0x08, 0x00 };
  wr(aht_bus, AHT_ADDR, &reset, 1);                            // soft reset
  delay_ms(20);
  if (!aht_wait_idle(200)) return false;
  wr(aht_bus, AHT_ADDR, cal, 3);                               // "may not succeed on newer AHT20s": result ignored
  if (!aht_wait_idle(200)) return false;
  int s = aht_status();
  return s >= 0 && (s & 0x08);                                  // calibrated
}

static bool aht_start(void) {
  static const uint8_t trig[3] = { 0xAC, 0x33, 0x00 };
  return wr(aht_bus, AHT_ADDR, trig, 3) == I2C_OK;
}

static uint8_t crc8_31(const uint8_t *p, int n) {             // AHT20 datasheet CRC: x^8+x^5+x^4+1, init 0xFF
  uint8_t c = 0xFF;
  while (n--) { c ^= *p++; for (int i = 0; i < 8; i++) c = (uint8_t)(c & 0x80 ? (c << 1) ^ 0x31 : c << 1); }
  return c;
}

static bool aht_finish(sensors_t *s) {                         // ~80 ms after aht_start
  uint8_t d[7];
  if (!aht_wait_idle(300) || i2c_xfer(aht_bus, AHT_ADDR, NULL, 0, d, 7) != I2C_OK) return false;
  uint32_t h = ((uint32_t)d[1] << 12) | ((uint32_t)d[2] << 4) | (d[3] >> 4);
  uint32_t t = ((uint32_t)(d[3] & 0x0F) << 16) | ((uint32_t)d[4] << 8) | d[5];
  s->aht_rh = (uint16_t)((h * 10000ull) >> 20);                // 0.01 %RH
  s->aht_t = (int16_t)((int32_t)((t * 20000ull) >> 20) - 5000);  // 0.01 C
  if (crc8_31(d, 6) != d[6]) s->status |= SENS_AHT_CRC;
  return true;
}

// ---------------------------------------------------------------- VEML7700 (Adafruit_VEML7700)
// 16-bit registers, LSB first. ALS_CONF 0x00: SD bit 0, IT bits 9:6, gain bits 12:11. 0x03 power save, 0x04 ALS,
// 0x05 WHITE. After clearing SD wait 2.5 ms (library: 5); a reading needs 2x the integration time (library, tested).
static int veml_w(uint8_t reg, uint16_t v) { uint8_t w[3] = { reg, (uint8_t)v, (uint8_t)(v >> 8) }; return wr(veml_bus, VEML_ADDR, w, 3); }
static int veml_r(uint8_t reg, uint16_t *v) {
  uint8_t b[2]; int rc = i2c_xfer(veml_bus, VEML_ADDR, &reg, 1, b, 2);
  if (rc == I2C_OK) *v = (uint16_t)(b[0] | (b[1] << 8));
  return rc;
}

static bool veml_one(uint16_t conf, uint32_t it_ms, uint16_t *als, uint16_t *white) {
  if (veml_w(0x00, conf | 1u) != I2C_OK) return false;        // shut down while changing settings
  veml_w(0x00, conf);                                           // on
  delay_ms(5 + 2 * it_ms);
  bool ok = veml_r(0x04, als) == I2C_OK && veml_r(0x05, white) == I2C_OK;
  veml_w(0x00, conf | 1u);                                      // shut down (~0.5 uA)
  return ok;
}

static bool veml_read(sensors_t *s) {
  if (veml_w(0x03, 0x0000) != I2C_OK) return false;           // power-save mode off (it's shut down between readings)
  return veml_one(0x0800, 100, &s->als[0], &s->white[0])       // gain 2 (01 << 11), IT 100 ms (0000 << 6)
      && veml_one(0x1300, 25, &s->als[1], &s->white[1]);       // gain 1/8 (10 << 11), IT 25 ms (1100 << 6)
}

// ---------------------------------------------------------------- AS7331 (SparkFun_AS7331, one-shot CMD mode)
// OSR 0x00 (both states): DOS bits 2:0 (2 = configuration, 3 = measurement), PD bit 6 (power down), SS bit 7 (start).
// Configuration state: AGEN 0x02 (ID 0x2x), CREG1 0x06 (gain code 7:4, time code 3:0), CREG2 0x07 (EN_TM bit 6),
// CREG3 0x08 (MMODE 7:6 = 01 CMD, CCLK 1:0 = 00 1.024 MHz), BREAK 0x09, EDGES 0x0A, OPTREG 0x0B (INIT_IDX bit 0).
// Measurement state: 0x00 = OSR + STATUS (NDATA bit 11, overflows bits 13-15), then TEMP, MRES1-3, LSB first.
// gain = 1 << (11 - code); time = 1 << code ms. uW/cm2 = counts * FSR / (gain * ms * 1024), FSR A/B/C =
// 348160 / 387072 / 169984.
static int as_w(uint8_t reg, uint8_t v) { uint8_t w[2] = { reg, v }; return wr(as_bus, AS_ADDR, w, 2); }
static int as_r(uint8_t reg, uint8_t *b, int n) { return i2c_xfer(as_bus, AS_ADDR, &reg, 1, b, (size_t)n); }

static bool as_init(void) {
  uint8_t id, v;
  if (as_w(0x00, 0x02) != I2C_OK) return false;                // configuration state, powered up
  if (as_r(0x02, &id, 1) != I2C_OK || (id >> 4) != 0x2) return false;
  if (as_r(0x07, &v, 1) == I2C_OK) as_w(0x07, (uint8_t)((v & 0x30) | 0x40));   // EN_TM, no divider (reserved kept)
  as_w(0x08, 0x40);                                            // CMD mode, CCLK 1.024 MHz, push-pull READY, no standby
  as_w(0x09, 25);                                              // BREAK 200 us (library default)
  as_w(0x0A, 1);                                               // EDGES (SYND only)
  if (as_r(0x0B, &v, 1) == I2C_OK) as_w(0x0B, (uint8_t)(v | 1)); // repeated start supported
  as_w(0x00, 0x42);                                            // powered down until the next reading
  return true;
}

static bool as_one(uint8_t creg1, uint16_t uv[3], uint16_t *temp, bool *ovf) {
  uint8_t b[8];
  if (as_w(0x00, 0x02) != I2C_OK) return false;                // configuration state, powered up
  as_w(0x06, creg1);
  as_w(0x00, 0x03);                                            // measurement state
  as_w(0x00, 0x83);                                            // start one conversion
  delay_ms(66);                                                // 64 ms conversion + margin
  uint32_t t0 = millis();
  for (;;) {                                                   // NDATA (STATUS bit 11) = the conversion is in
    if (as_r(0x00, b, 2) != I2C_OK) return false;
    if ((b[1] & 0x08) || millis() - t0 > 100) break;
    delay_ms(2);
  }
  *ovf = (b[1] & 0xE0) != 0;                                   // ADCOF, MRESOF, OUTCONVOF
  if (!(b[1] & 0x08) || as_r(0x01, b, 8) != I2C_OK) return false;
  *temp = (uint16_t)(b[0] | (b[1] << 8));
  for (int i = 0; i < 3; i++) uv[i] = (uint16_t)(b[2 + 2 * i] | (b[3 + 2 * i] << 8));
  return true;
}

static bool as_read(sensors_t *s) {
  bool o0 = false, o1 = false;
  bool ok = as_one(0x36, s->uv[0], &s->as_temp, &o0)            // gain 256 (code 3), 64 ms (code 6)
         && as_one(0x76, s->uv[1], &s->as_temp, &o1);           // gain 16 (code 7), 64 ms
  as_w(0x00, 0x42);                                            // configuration state, powered down
  if (o0) s->status |= SENS_AS_OVF0;
  if (o1) s->status |= SENS_AS_OVF1;
  return ok;
}

// ---------------------------------------------------------------- all of them
void sensors_read(sensors_t *s) {
  memset(s, 0, sizeof *s);
  if (!aht_bus)  { aht_bus = find(AHT_ADDR); aht_ready = false; }
  if (!veml_bus) veml_bus = find(VEML_ADDR);
  if (!as_bus)   { as_bus = find(AS_ADDR); as_ready = false; }
  if (aht_bus) i2c_init(aht_bus);
  if (veml_bus && veml_bus != aht_bus) i2c_init(veml_bus);
  if (as_bus && as_bus != aht_bus && as_bus != veml_bus) i2c_init(as_bus);

  if (aht_bus && !aht_ready) aht_ready = aht_init();
  bool aht_go = aht_bus && aht_ready && aht_start();           // the AHT20 converts while the others are read
  if (veml_bus) { if (veml_read(s)) s->status |= SENS_VEML; else veml_bus = 0; }
  if (as_bus && !as_ready) as_ready = as_init();
  if (as_bus && as_ready) { if (as_read(s)) s->status |= SENS_AS; else as_bus = 0; }
  else if (as_bus) as_bus = 0;
  if (aht_go && aht_finish(s)) s->status |= SENS_AHT;
  else if (aht_bus) { aht_bus = 0; s->status &= (uint8_t)~SENS_AHT_CRC; }   // look for it again next time
}

static void put_c100(const char *what, int v, const char *unit) {
  cprintf("%s%s%d.%02d %s", what, v < 0 ? "-" : "", (v < 0 ? -v : v) / 100, (v < 0 ? -v : v) % 100, unit);
}

void sensors_print(const sensors_t *s) {
  if (s->status & SENS_AHT) {
    put_c100("  AHT20     ", s->aht_t, "C, ");
    put_c100("", s->aht_rh, "%RH");
    cputs(s->status & SENS_AHT_CRC ? "  (CRC mismatch)\n" : "\n");
  } else cputs("  AHT20     not found\n");
  if (s->status & SENS_VEML)                                   // lux/count: 0.0288 (shade), 1.8432 (sun)
    cprintf("  VEML7700  shade %u / white %u (~%lu lux), sun %u / white %u (~%lu lux)\n", s->als[0], s->white[0],
            (unsigned long)s->als[0] * 288u / 10000u, s->als[1], s->white[1], (unsigned long)s->als[1] * 18432u / 10000u);
  else cputs("  VEML7700  not found\n");
  if (s->status & SENS_AS) {                                   // uW/cm2 per count: shade A 0.0208, sun A 0.332
    cprintf("  AS7331    shade A/B/C %u %u %u%s, sun %u %u %u%s (UVA ~%lu uW/cm2)", s->uv[0][0], s->uv[0][1], s->uv[0][2],
            s->status & SENS_AS_OVF0 ? " OVERFLOW" : "", s->uv[1][0], s->uv[1][1], s->uv[1][2],
            s->status & SENS_AS_OVF1 ? " OVERFLOW" : "", (unsigned long)s->uv[1][0] * 332u / 1000u);
    put_c100(", chip ", (int)s->as_temp * 5 - 6690, "C\n");
  } else cputs("  AS7331    not found\n");
}
