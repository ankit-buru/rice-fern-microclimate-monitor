#include <string.h>
#include "hw.h"

static volatile uint32_t ticks;
static uint32_t reset_flags;

void SysTick_Handler(void) { ticks++; }
uint32_t millis(void) { return ticks; }

void delay_ms(uint32_t ms) {
  uint32_t t0 = ticks;
  while (ticks - t0 < ms) system_poll();
}

// ---------------------------------------------------------------- ROM bootloader
// A RAM word outside .bss/.data (linker section .noinit) survives the software reset. The jump happens before
// anything is initialised, so the bootloader starts from a reset-like state. The system memory address (0x1FF00000
// on STM32L07x) is from memory, not checked against AN2606: if "dfu" doesn't enumerate as 0483:df11, use BOOT0 + RESET.
#define DFU_MAGIC     0xDF00B007u
#define SYSMEM_BASE   0x1FF00000u
__attribute__((section(".noinit"))) static uint32_t dfu_request;

void hw_enter_bootloader(void) {
  dfu_request = DFU_MAGIC;
  NVIC_SystemReset();
}

void hw_early(void) {
  reset_flags = RCC->CSR;
  RCC->CSR |= RCC_CSR_RMVF;                                   // clear the flags for next time
  if (dfu_request != DFU_MAGIC) return;
  dfu_request = 0;
  uint32_t sp = *(volatile uint32_t *)SYSMEM_BASE, pc = *(volatile uint32_t *)(SYSMEM_BASE + 4);
  if (sp < SRAM_BASE || sp > SRAM_BASE + 20 * 1024) return;   // not a vector table: boot normally
  RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
  SYSCFG->CFGR1 = (SYSCFG->CFGR1 & ~SYSCFG_CFGR1_MEM_MODE) | SYSCFG_CFGR1_MEM_MODE_0;   // system flash at 0x0
  __set_MSP(sp);
  ((void (*)(void))pc)();
}

uint32_t hw_reset_flags(void) { return reset_flags; }

const char *hw_reset_cause(void) {   // most specific first: a pin reset is also flagged on most of the others
  if (reset_flags & RCC_CSR_IWDGRSTF) return "independent watchdog";
  if (reset_flags & RCC_CSR_WWDGRSTF) return "window watchdog";
  if (reset_flags & RCC_CSR_LPWRRSTF) return "low-power";
  if (reset_flags & RCC_CSR_SFTRSTF)  return "software";
  if (reset_flags & RCC_CSR_PORRSTF)  return "power-on";
  if (reset_flags & RCC_CSR_FWRSTF)   return "firewall";
  if (reset_flags & RCC_CSR_OBLRSTF)  return "option-byte load";
  if (reset_flags & RCC_CSR_PINRSTF)  return "NRST pin";
  return "unknown";
}

void hw_uid(uint32_t uid[3]) {   // words at UID_BASE + 0x00, + 0x04, + 0x14 (RM0376 layout, from memory: not checked)
  const volatile uint32_t *u = (const volatile uint32_t *)UID_BASE;
  uid[0] = u[0]; uid[1] = u[1]; uid[2] = u[5];
}

unsigned hw_flash_kb(void) { return *(const volatile uint16_t *)FLASHSIZE_BASE; }

// ---------------------------------------------------------------- clocks
void hw_init(void) {
  // core voltage range 1 (1.8 V) + 1 flash wait state: valid at 16 MHz whatever the defaults are
  RCC->APB1ENR |= RCC_APB1ENR_PWREN;
  PWR->CR = (PWR->CR & ~PWR_CR_VOS) | PWR_CR_VOS_0;
  while (PWR->CSR & PWR_CSR_VOSF) {}
  FLASH->ACR |= FLASH_ACR_LATENCY | FLASH_ACR_PRFTEN;

  // SYSCLK = HSI16
  RCC->CR |= RCC_CR_HSION;
  while (!(RCC->CR & RCC_CR_HSIRDY)) {}
  RCC->CFGR = (RCC->CFGR & ~RCC_CFGR_SW) | RCC_CFGR_SW_HSI;
  while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_HSI) {}
  SystemCoreClock = 16000000u;

  // USB: HSI48 (needs the VREFINT buffer for HSI48), trimmed to the host's 1 ms SOF by the CRS (crystal-less USB)
  RCC->APB2ENR |= RCC_APB2ENR_SYSCFGEN;
  SYSCFG->CFGR3 |= SYSCFG_CFGR3_EN_VREFINT | SYSCFG_CFGR3_ENREF_HSI48;
  while (!(SYSCFG->CFGR3 & SYSCFG_CFGR3_VREFINT_RDYF)) {}
  RCC->CRRCR |= RCC_CRRCR_HSI48ON;
  while (!(RCC->CRRCR & RCC_CRRCR_HSI48RDY)) {}
  RCC->CCIPR |= RCC_CCIPR_HSI48SEL;                           // 48 MHz clock = HSI48 (not the PLL)
  RCC->APB1ENR |= RCC_APB1ENR_CRSEN | RCC_APB1ENR_USBEN;
  CRS->CR |= CRS_CR_AUTOTRIMEN | CRS_CR_CEN;                  // reset CFGR already = sync on USB SOF, reload 47999

  SysTick_Config(16000);                                      // 1 ms

  // GPIO: everything starts in the safe state of DESIGN.md §8 (modem rail off, shifter-side lines as inputs)
  RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN | RCC_IOPENR_GPIOCEN | RCC_IOPENR_GPIOHEN;
  pin_output(MDM_PWR_EN, 0);
  pin_output(MDM_PWRKEY, 0);
  pin_output(GNSS_ANT_EN, 0);
  pin_output(LED_USER, 0);
  pin_t inputs[] = { MDM_STATUS, MDM_RXD, MDM_TXD, MDM_CTS, MDM_RTS, MDM_DCD, MDM_DTR, MDM_RI, SIM_DET, BAT_ALRT };
  for (unsigned i = 0; i < sizeof inputs / sizeof inputs[0]; i++) { pin_pull(inputs[i], PULL_NONE); pin_mode(inputs[i], MODE_IN); }
  pin_pull(GNSS_ANT_FLT, PULL_UP); pin_mode(GNSS_ANT_FLT, MODE_IN);   // U10 OC is open drain (DESIGN.md §8)
  pin_mode(PIN(A, 11), MODE_IN); pin_mode(PIN(A, 12), MODE_IN);      // USB DM/DP: the USB peripheral takes over
}

// ---------------------------------------------------------------- independent watchdog
// Keys 0xCCCC (start), 0x5555 (unlock PR/RLR), 0xAAAA (reload): the usual STM32 IWDG values, as remembered.
// A software reset stops it, and hw_early() jumps to the ROM bootloader before it could be restarted, so "dfu"
// still works after field mode.
static bool wdg_running;

void hw_watchdog_start(void) {
  if (wdg_running) return;
  IWDG->KR = 0xCCCC;
  IWDG->KR = 0x5555;
  IWDG->PR = 6;                                               // LSI / 256
  IWDG->RLR = 4095;
  uint32_t t0 = millis();
  while ((IWDG->SR & (IWDG_SR_PVU | IWDG_SR_RVU)) && millis() - t0 < 100) {}
  IWDG->KR = 0xAAAA;
  wdg_running = true;
}

void hw_watchdog_kick(void) { if (wdg_running) IWDG->KR = 0xAAAA; }
bool hw_watchdog_running(void) { return wdg_running; }

// ---------------------------------------------------------------- analog: VDDA (VREFINT) and the MCU temperature sensor
#define VREFINT_CAL (*(const volatile uint16_t *)0x1FF80078u)   // raw VREFINT at VDDA = 3.0 V, 25 C (DS10689 Table 26)
#define TS_CAL1     (*(const volatile uint16_t *)0x1FF8007Au)   // raw TSENSE at 30 C, VDDA = 3.0 V (DS10689 Table 68)
#define TS_CAL2     (*(const volatile uint16_t *)0x1FF8007Eu)   // raw TSENSE at 130 C, VDDA = 3.0 V

static void adc_on(void) {
  RCC->APB2ENR |= RCC_APB2ENR_ADCEN;
  ADC1->CFGR2 = (ADC1->CFGR2 & ~ADC_CFGR2_CKMODE) | ADC_CFGR2_CKMODE_0;   // PCLK / 2 = 8 MHz
  if (!(ADC1->CR & ADC_CR_ADEN)) {
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) {}
  }
  ADC->CCR |= ADC_CCR_VREFEN | ADC_CCR_TSEN;
  ADC1->ISR = ADC_ISR_ADRDY;
  ADC1->CR |= ADC_CR_ADEN;
  while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
  ADC1->SMPR = ADC_SMPR_SMP;                                  // 160.5 cycles = 20 us (VREFINT and TSENSE need >= 10 us)
  delay_ms(1);                                                // VREFINT and TSENSE start-up
}

static void adc_off(void) {
  ADC1->CR |= ADC_CR_ADDIS;
  while (ADC1->CR & ADC_CR_ADEN) {}
  ADC->CCR &= ~(ADC_CCR_VREFEN | ADC_CCR_TSEN);
  RCC->APB2ENR &= ~RCC_APB2ENR_ADCEN;
}

static uint32_t adc_sum8(uint32_t chsel) {
  ADC1->CHSELR = chsel;
  uint32_t sum = 0;
  for (int i = 0; i < 8; i++) {
    ADC1->CR |= ADC_CR_ADSTART;
    while (!(ADC1->ISR & ADC_ISR_EOC)) {}
    sum += ADC1->DR;
  }
  return sum;
}

unsigned hw_vdda_mv(void) {
  adc_on();
  uint32_t vref = adc_sum8(ADC_CHSELR_CHSEL17);
  adc_off();
  return vref ? (unsigned)(3000u * VREFINT_CAL * 8u / vref) : 0;
}

int hw_mcu_temp_dc(void) {                                    // TSENSE scaled to VDDA = 3.0 V, then the two-point cal
  adc_on();
  uint32_t vref = adc_sum8(ADC_CHSELR_CHSEL17), ts = adc_sum8(ADC_CHSELR_CHSEL18);
  adc_off();
  if (!vref || TS_CAL2 <= TS_CAL1) return -9999;
  int32_t ts3 = (int32_t)(ts * VREFINT_CAL / vref);          // = raw TSENSE at VDDA = 3.0 V (both are sums of 8)
  return 300 + (ts3 - (int32_t)TS_CAL1) * 1000 / ((int32_t)TS_CAL2 - (int32_t)TS_CAL1);
}

// ---------------------------------------------------------------- data EEPROM (6 KB, word writes, 3.3 ms each)
// Unlock PECR with the two PEKEYR keys, store each word (the hardware erases and programs it), wait for BSY, lock.
// Unchanged words are skipped: less wear, and faster. The key values are ST's FLASH_PEKEY1/2 as remembered
// (RM0376 is not local): the read-back catches a mistake.
bool hw_eeprom_write(uint32_t addr, const void *src, size_t n) {
  const uint8_t *s = src;
  volatile uint32_t *dst = (volatile uint32_t *)addr;
  if ((addr & 3) || (n & 3) || addr < DATA_EEPROM_BASE || addr + n > DATA_EEPROM_BANK2_END + 1) return false;
  while (FLASH->SR & FLASH_SR_BSY) {}
  if (FLASH->PECR & FLASH_PECR_PELOCK) { FLASH->PEKEYR = 0x89ABCDEFu; FLASH->PEKEYR = 0x02030405u; }
  for (size_t i = 0; i < n / 4; i++) {
    uint32_t w; memcpy(&w, s + 4 * i, 4);
    if (dst[i] == w) continue;
    dst[i] = w;
    while (FLASH->SR & FLASH_SR_BSY) {}
    FLASH->SR = FLASH_SR_EOP;
    hw_watchdog_kick();
  }
  FLASH->PECR |= FLASH_PECR_PELOCK;
  return memcmp((const void *)addr, src, n) == 0;
}

// ---------------------------------------------------------------- LSE crystal Y1
bool hw_lse_ready(void) { return RCC->CSR & RCC_CSR_LSERDY; }

int hw_lse_start(unsigned drive, uint32_t timeout_ms) {
  PWR->CR |= PWR_CR_DBP;                                      // RCC_CSR LSE/RTC bits are in the backup domain
  if (RCC->CSR & RCC_CSR_LSEON) {                             // restart from off so the start time means something
    RCC->CSR &= ~RCC_CSR_LSEON;
    while (RCC->CSR & RCC_CSR_LSERDY) {}
  }
  RCC->CSR = (RCC->CSR & ~(RCC_CSR_LSEDRV | RCC_CSR_LSEBYP)) | ((drive & 3u) << RCC_CSR_LSEDRV_Pos);
  RCC->CSR |= RCC_CSR_LSEON;
  uint32_t t0 = millis();
  while (!(RCC->CSR & RCC_CSR_LSERDY)) {
    if (millis() - t0 > timeout_ms) return -1;
    system_poll();
  }
  return (int)(millis() - t0);
}

// ---------------------------------------------------------------- device clock: the RTC, kept running across resets
// The calendar counts from 2000-01-01 00:00:00 when the clock (re)starts; hw_clock_s() turns it into plain seconds.
// It's in the backup domain, so it survives system resets (watchdog, RESET, reflashing) but not a power cut.
// BYPSHAD: reads go straight to the counters (no waiting for a shadow resync after Stop): read twice, compare.
static volatile bool rtc_woke;
static uint32_t rtc_hz;                                       // RTC clock: 32768 (LSE) or ~37000 (LSI fallback), 0 = not set up
static uint32_t prediv_s = 255;
static bool clock_fresh;

void RTC_IRQHandler(void) {
  if (RTC->ISR & RTC_ISR_WUTF) { RTC->ISR &= ~RTC_ISR_WUTF; rtc_woke = true; }   // RTC_ISR[13:8] aren't write-protected
  EXTI->PR = EXTI_PR_PIF20;
}

static void rtc_calendar_zero(bool lse) {
  RTC->WPR = 0xCA; RTC->WPR = 0x53;
  RTC->ISR |= RTC_ISR_INIT;
  while (!(RTC->ISR & RTC_ISR_INITF)) {}
  RTC->PRER = (127u << 16) | (lse ? 255u : 288u);             // 1 Hz: 32768/128/256, or ~37000/128/289 on the LSI
  RTC->TR = 0; RTC->DR = 0x2101;                              // 2000-01-01 (a Saturday, but WDU isn't used) 00:00:00
  RTC->ISR &= ~RTC_ISR_INIT;
  RTC->WPR = 0xFF;
}

bool hw_clock_init(void) {
  if (rtc_hz) return rtc_hz == 32768u;
  RCC->APB1ENR |= RCC_APB1ENR_PWREN;
  PWR->CR |= PWR_CR_DBP;
  uint32_t sel = RCC->CSR & RCC_CSR_RTCSEL;
  bool running = (RCC->CSR & RCC_CSR_RTCEN) && (RTC->ISR & RTC_ISR_INITS);
  bool lse;
  if (running && sel == RCC_CSR_RTCSEL_LSE && hw_lse_ready()) lse = true;            // carry on counting
  else if (running && sel == RCC_CSR_RTCSEL_LSI) { RCC->CSR |= RCC_CSR_LSION; while (!(RCC->CSR & RCC_CSR_LSIRDY)) {} lse = false; }
  else {                                                       // first start since the cell was connected (or a fault)
    lse = hw_lse_ready() || hw_lse_start(2, 3000) >= 0;        // drive >= medium-high for Y1 (DESIGN.md §4.3)
    uint32_t want = lse ? RCC_CSR_RTCSEL_LSE : RCC_CSR_RTCSEL_LSI;
    if (sel && sel != want) {                                 // RTCSEL can only change after a backup-domain reset
      RCC->CSR |= RCC_CSR_RTCRST; RCC->CSR &= ~RCC_CSR_RTCRST;  // (which also stops the LSE: restart it)
      if (lse) lse = hw_lse_start(2, 3000) >= 0;
      want = lse ? RCC_CSR_RTCSEL_LSE : RCC_CSR_RTCSEL_LSI;
    }
    if (!lse) { RCC->CSR |= RCC_CSR_LSION; while (!(RCC->CSR & RCC_CSR_LSIRDY)) {} }
    RCC->CSR = (RCC->CSR & ~RCC_CSR_RTCSEL) | want | RCC_CSR_RTCEN;
    rtc_calendar_zero(lse);
    clock_fresh = true;
  }
  prediv_s = RTC->PRER & 0x7FFFu;
  RTC->WPR = 0xCA; RTC->WPR = 0x53;
  RTC->CR = (RTC->CR & ~(RTC_CR_WUTE | RTC_CR_WUTIE)) | RTC_CR_BYPSHAD;
  RTC->WPR = 0xFF;
  EXTI->IMR |= EXTI_IMR_IM20; EXTI->RTSR |= EXTI_RTSR_RT20;  // line 20 = RTC wakeup timer
  NVIC_SetPriority(RTC_IRQn, 2); NVIC_EnableIRQ(RTC_IRQn);
  RCC->CFGR |= RCC_CFGR_STOPWUCK;                             // wake up from Stop on HSI16
  PWR->CR |= PWR_CR_LPSDSR | PWR_CR_ULP | PWR_CR_FWU;         // low-power regulator in Stop, VREFINT off, don't wait for it
  rtc_hz = lse ? 32768u : 37000u;
  return lse;
}

bool hw_clock_fresh(void) { return clock_fresh; }

static uint32_t days_since_2000(unsigned y, unsigned m, unsigned d) {   // y 0..99 (2000..2099; 2000 is a leap year)
  static const uint16_t before[12] = { 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334 };
  if (m < 1 || m > 12) m = 1;
  uint32_t days = y * 365u + (y + 3u) / 4u + before[m - 1] + d - 1u;
  if (m > 2 && y % 4u == 0) days++;
  return days;
}

uint32_t hw_clock_read(uint32_t *ms) {
  if (!rtc_hz) hw_clock_init();
  uint32_t ss, tr, dr;
  do { ss = RTC->SSR; tr = RTC->TR; dr = RTC->DR; } while (ss != RTC->SSR || tr != RTC->TR);
  unsigned h = ((tr >> 20) & 3) * 10 + ((tr >> 16) & 0xF), mi = ((tr >> 12) & 7) * 10 + ((tr >> 8) & 0xF);
  unsigned s = ((tr >> 4) & 7) * 10 + (tr & 0xF);
  unsigned y = ((dr >> 20) & 0xF) * 10 + ((dr >> 16) & 0xF), mo = ((dr >> 12) & 1) * 10 + ((dr >> 8) & 0xF);
  unsigned d = ((dr >> 4) & 3) * 10 + (dr & 0xF);
  if (ms) *ms = ss <= prediv_s ? (prediv_s - ss) * 1000u / (prediv_s + 1u) : 0;
  return days_since_2000(y, mo, d) * 86400u + h * 3600u + mi * 60u + s;
}

uint32_t hw_clock_s(void) { return hw_clock_read(NULL); }

uint32_t hw_bkp_read(unsigned i) { return i < 5 ? (&RTC->BKP0R)[i] : 0; }
void hw_bkp_write(unsigned i, uint32_t v) { PWR->CR |= PWR_CR_DBP; if (i < 5) (&RTC->BKP0R)[i] = v; }

// ---------------------------------------------------------------- Stop mode (RM0376 "Stop mode", DS10689 §6.3.4/6.3.5)
// Woken by the RTC wakeup timer (EXTI line 20) clocked from RTC/16: 2048 Hz on the LSE. The core restarts on
// HSI16 (STOPWUCK), the clock it was already on, so nothing needs reconfiguring except HSI48 (stopped in Stop).
// SysTick doesn't run in Stop: the requested time is added to millis() afterwards, so timeouts stay right.
// Inputs with no pull (the shifter-side modem lines, Hi-Z while the modem is off) would float: analog mode while asleep.
static uint32_t saved_moder[4];
static GPIO_TypeDef *const ports[4] = { GPIOA, GPIOB, GPIOC, GPIOH };

static void park_inputs(void) {
  for (int i = 0; i < 4; i++) {
    uint32_t m = ports[i]->MODER, pu = ports[i]->PUPDR, out = m;
    saved_moder[i] = m;
    for (int p = 0; p < 16; p++)
      if (((m >> (2 * p)) & 3u) == MODE_IN && ((pu >> (2 * p)) & 3u) == PULL_NONE) out |= 3u << (2 * p);
    ports[i]->MODER = out;
  }
}
static void unpark_inputs(void) { for (int i = 0; i < 4; i++) ports[i]->MODER = saved_moder[i]; }

void hw_stop_ms(uint32_t ms) {
  if (!rtc_hz) hw_clock_init();
  if (ms > 30000) ms = 30000;                                 // 16-bit counter at 2048 Hz: 32 s max
  uint32_t n = (uint32_t)((uint64_t)ms * (rtc_hz / 16u) / 1000u);
  if (n < 2) n = 2;
  while (!(USART1->ISR & USART_ISR_TC)) {}                    // let the debug UART finish its last byte
  RTC->WPR = 0xCA; RTC->WPR = 0x53;
  RTC->CR &= ~RTC_CR_WUTE;
  while (!(RTC->ISR & RTC_ISR_WUTWF)) {}
  RTC->WUTR = n - 1;
  RTC->CR = (RTC->CR & ~RTC_CR_WUCKSEL) | RTC_CR_WUTIE | RTC_CR_WUTE;   // WUCKSEL 000 = RTC/16
  RTC->WPR = 0xFF;
  RTC->ISR &= ~RTC_ISR_WUTF; EXTI->PR = EXTI_PR_PIF20;
  PWR->CR |= PWR_CR_CWUF;
  park_inputs();
  uint32_t systick = SysTick->CTRL;
  SysTick->CTRL = systick & ~SysTick_CTRL_TICKINT_Msk;        // no tick interrupt to cut the sleep short
  PWR->CR &= ~PWR_CR_PDDS;                                    // Stop, not Standby
  SCB->SCR |= SCB_SCR_SLEEPDEEP_Msk;
  rtc_woke = false;
  while (!rtc_woke) __WFI();                                  // anything else that wakes us: back to sleep
  SCB->SCR &= ~SCB_SCR_SLEEPDEEP_Msk;
  SysTick->CTRL = systick;
  unpark_inputs();
  RTC->WPR = 0xCA; RTC->WPR = 0x53; RTC->CR &= ~(RTC_CR_WUTE | RTC_CR_WUTIE); RTC->WPR = 0xFF;
  ticks += ms;
}

void hw_usb_clock_resume(void) {                              // HSI48 back after Stop (it needs the VREFINT buffer)
  SYSCFG->CFGR3 |= SYSCFG_CFGR3_EN_VREFINT | SYSCFG_CFGR3_ENREF_HSI48;
  uint32_t t0 = millis();
  while (!(SYSCFG->CFGR3 & SYSCFG_CFGR3_VREFINT_RDYF) && millis() - t0 < 10) {}
  RCC->CRRCR |= RCC_CRRCR_HSI48ON;
  while (!(RCC->CRRCR & RCC_CRRCR_HSI48RDY) && millis() - t0 < 20) {}
}

