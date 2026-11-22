// Qwiic sensors under test: AHT20 (temperature/humidity), VEML7700 (visible light), AS7331 (UVA/UVB/UVC).
// Each is looked for on both Qwiic buses (J3 = I2C2, J11 = I2C3), so either connector works. Light and UV are read
// at two fixed settings, "shade" (sensitive) and "sun" (wide range); the server picks the unsaturated one.
// Register sequences follow the vendors' drivers (Adafruit_AHTX0, Adafruit_VEML7700, SparkFun_AS7331), 2026-11.
#pragma once
#include <stdbool.h>
#include <stdint.h>

enum {                              // sensors_t.status
  SENS_AHT      = 0x01,             // AHT20 answered and its reading is in
  SENS_VEML     = 0x02,             // VEML7700 ...
  SENS_AS       = 0x04,             // AS7331 ...
  SENS_AS_OVF0  = 0x08,             // AS7331 shade reading overflowed (ADCOF/MRESOF/OUTCONVOF)
  SENS_AS_OVF1  = 0x10,             // AS7331 sun reading overflowed
  SENS_AHT_CRC  = 0x20,             // AHT20 CRC didn't match (reading kept anyway)
};

typedef struct {
  uint8_t  status;                  // SENS_*
  int16_t  aht_t;                   // 0.01 C
  uint16_t aht_rh;                  // 0.01 %RH
  uint16_t als[2], white[2];        // VEML7700 counts: [0] shade = gain 2, 100 ms; [1] sun = gain 1/8, 25 ms
  uint16_t uv[2][3];                // AS7331 UVA, UVB, UVC counts: [0] shade = gain 256, 64 ms; [1] sun = gain 16, 64 ms
  uint16_t as_temp;                 // AS7331 chip temperature, raw (C = raw * 0.05 - 66.9)
} sensors_t;

void sensors_read(sensors_t *s);    // finds the sensors if needed, takes one reading of each (~0.4 s)
void sensors_print(const sensors_t *s);
