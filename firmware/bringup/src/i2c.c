#include "i2c.h"
#include "hw.h"

typedef struct {
  I2C_TypeDef *r;
  pin_t scl, sda;
  uint8_t af_scl, af_sda;
  volatile uint32_t *enr;
  uint32_t enbit;
  const char *name;
} bus_t;

static const bus_t *bus(int n) {
  static const bus_t b[3] = {
    { I2C1, I2C1_SCL, I2C1_SDA, 4, 1, &RCC->APB1ENR, RCC_APB1ENR_I2C1EN, "I2C1 (fuel gauge U8)" },
    { I2C2, I2C2_SCL, I2C2_SDA, 5, 6, &RCC->APB1ENR, RCC_APB1ENR_I2C2EN, "I2C2 (Qwiic J3)" },
    { I2C3, I2C3_SCL, I2C3_SDA, 7, 7, &RCC->APB1ENR, RCC_APB1ENR_I2C3EN, "I2C3 (Qwiic J11)" },
  };
  return &b[(n >= 1 && n <= 3 ? n : 1) - 1];
}

const char *i2c_name(int n) { return bus(n)->name; }

void i2c_lines(int n, bool *scl, bool *sda) {
  const bus_t *b = bus(n);
  b->r->CR1 &= ~I2C_CR1_PE;
  pin_pull(b->scl, PULL_NONE); pin_pull(b->sda, PULL_NONE);
  pin_mode(b->scl, MODE_IN);  pin_mode(b->sda, MODE_IN);
  delay_ms(1);
  *scl = pin_read(b->scl); *sda = pin_read(b->sda);
}

bool i2c_recover(int n) {
  const bus_t *b = bus(n);
  b->r->CR1 &= ~I2C_CR1_PE;
  pin_open_drain(b->scl, true);
  pin_mode(b->sda, MODE_IN);
  for (int i = 0; i < 9 && !pin_read(b->sda); i++) {          // clock until the device lets SDA go
    pin_output(b->scl, 0); for (volatile int d = 0; d < 80; d++) {}
    pin_output(b->scl, 1); for (volatile int d = 0; d < 80; d++) {}
  }
  pin_mode(b->scl, MODE_IN);
  return pin_read(b->sda);
}

void i2c_init(int n) {
  const bus_t *b = bus(n);
  *b->enr |= b->enbit;
  pin_open_drain(b->scl, true); pin_open_drain(b->sda, true);  // external pull-ups only (R41/R42, R12/R13, R43/R44)
  pin_pull(b->scl, PULL_NONE);  pin_pull(b->sda, PULL_NONE);
  pin_af(b->scl, b->af_scl);    pin_af(b->sda, b->af_sda);
  b->r->CR1 = 0;
  // 100 kHz from I2CCLK = PCLK1 = 16 MHz: PRESC 3 (250 ns), SCLL 0x13 (5.0 us), SCLH 0x0F (4.0 us), SDADEL 2,
  // SCLDEL 4. These are the reference manual's 16 MHz standard-mode values as remembered: check SCL on a scope.
  b->r->TIMINGR = 0x30420F13u;
  b->r->CR1 = I2C_CR1_PE;
}

static int wait(I2C_TypeDef *r, uint32_t flag) {
  uint32_t t0 = millis();
  while (!(r->ISR & flag)) {
    if (r->ISR & I2C_ISR_NACKF) return I2C_NACK;
    if (millis() - t0 > 10) return I2C_TIMEOUT;
  }
  return I2C_OK;
}

static int finish(I2C_TypeDef *r, int rc) {
  if (rc != I2C_OK && !(r->ISR & I2C_ISR_STOPF)) r->CR2 |= I2C_CR2_STOP;
  uint32_t t0 = millis();
  while (!(r->ISR & I2C_ISR_STOPF) && millis() - t0 < 10) {}
  r->ICR = I2C_ICR_STOPCF | I2C_ICR_NACKCF;
  if (rc == I2C_TIMEOUT) { r->CR1 &= ~I2C_CR1_PE; r->CR1 |= I2C_CR1_PE; }   // reset the state machine
  return rc;
}

int i2c_xfer(int n, uint8_t addr, const uint8_t *w, size_t wn, uint8_t *rd, size_t rn) {
  I2C_TypeDef *r = bus(n)->r;
  int rc = I2C_OK;
  r->ICR = I2C_ICR_STOPCF | I2C_ICR_NACKCF;
  if (wn || !rn) {                                             // write phase (also the zero-length probe)
    r->CR2 = ((uint32_t)addr << 1) | (wn << I2C_CR2_NBYTES_Pos) | (rn ? 0 : I2C_CR2_AUTOEND) | I2C_CR2_START;
    for (size_t i = 0; i < wn && rc == I2C_OK; i++)
      if ((rc = wait(r, I2C_ISR_TXIS)) == I2C_OK) r->TXDR = w[i];
    if (rc == I2C_OK && rn) rc = wait(r, I2C_ISR_TC);
    if (rc == I2C_OK && !rn) return finish(r, (r->ISR & I2C_ISR_NACKF) ? I2C_NACK : wait(r, I2C_ISR_STOPF));
    if (rc != I2C_OK) return finish(r, rc);
  }
  r->CR2 = ((uint32_t)addr << 1) | I2C_CR2_RD_WRN | (rn << I2C_CR2_NBYTES_Pos) | I2C_CR2_AUTOEND | I2C_CR2_START;
  for (size_t i = 0; i < rn && rc == I2C_OK; i++)
    if ((rc = wait(r, I2C_ISR_RXNE)) == I2C_OK) rd[i] = (uint8_t)r->RXDR;
  if (rc == I2C_OK) rc = wait(r, I2C_ISR_STOPF);
  return finish(r, rc);
}

bool i2c_probe(int n, uint8_t addr) { return i2c_xfer(n, addr, NULL, 0, NULL, 0) == I2C_OK; }

int i2c_read_reg16(int n, uint8_t addr, uint8_t reg, uint16_t *v) {
  uint8_t b[2];
  int rc = i2c_xfer(n, addr, &reg, 1, b, 2);
  if (rc == I2C_OK) *v = (uint16_t)((b[0] << 8) | b[1]);
  return rc;
}
