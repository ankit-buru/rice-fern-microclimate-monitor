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

// ---------------------------------------------------------------- VDDA from VREFINT
#define VREFINT_CAL (*(const volatile uint16_t *)0x1FF80078u)   // raw VREFINT at VDDA = 3.0 V, 25 C (DS10689, VREFINT_CAL)

unsigned hw_vdda_mv(void) {
  RCC->APB2ENR |= RCC_APB2ENR_ADCEN;
  ADC1->CFGR2 = (ADC1->CFGR2 & ~ADC_CFGR2_CKMODE) | ADC_CFGR2_CKMODE_0;   // PCLK / 2 = 8 MHz
  if (!(ADC1->CR & ADC_CR_ADEN)) {
    ADC1->CR |= ADC_CR_ADCAL;
    while (ADC1->CR & ADC_CR_ADCAL) {}
  }
  ADC->CCR |= ADC_CCR_VREFEN;
  ADC1->ISR = ADC_ISR_ADRDY;
  ADC1->CR |= ADC_CR_ADEN;
  while (!(ADC1->ISR & ADC_ISR_ADRDY)) {}
  ADC1->CHSELR = ADC_CHSELR_CHSEL17;                          // VREFINT
  ADC1->SMPR = ADC_SMPR_SMP;                                  // 160.5 cycles = 20 us (VREFINT needs >= 10 us)
  delay_ms(1);                                                // VREFINT start-up
  uint32_t sum = 0;
  for (int i = 0; i < 8; i++) {
    ADC1->CR |= ADC_CR_ADSTART;
    while (!(ADC1->ISR & ADC_ISR_EOC)) {}
    sum += ADC1->DR;
  }
  ADC1->CR |= ADC_CR_ADDIS;
  while (ADC1->CR & ADC_CR_ADEN) {}
  ADC->CCR &= ~ADC_CCR_VREFEN;
  return sum ? (unsigned)(3000u * VREFINT_CAL * 8u / sum) : 0;
}

// ---------------------------------------------------------------- LSE + RTC
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

void hw_rtc_start(void) {
  PWR->CR |= PWR_CR_DBP;
  RCC->CSR = (RCC->CSR & ~RCC_CSR_RTCSEL) | RCC_CSR_RTCSEL_LSE | RCC_CSR_RTCEN;
  RTC->WPR = 0xCA; RTC->WPR = 0x53;                           // unlock
  RTC->ISR |= RTC_ISR_INIT;
  while (!(RTC->ISR & RTC_ISR_INITF)) {}
  RTC->PRER = (127u << 16) | 255u;                            // 32768 / 128 / 256 = 1 Hz
  RTC->TR = 0; RTC->DR = 0x2101;                              // 00:00:00 (date unused)
  RTC->ISR &= ~RTC_ISR_INIT;
  RTC->WPR = 0xFF;                                            // lock
}

uint32_t hw_rtc_seconds(void) {
  uint32_t tr = RTC->TR; (void)RTC->DR;                       // reading TR locks the shadow registers until DR is read
  unsigned h = ((tr >> 20) & 3) * 10 + ((tr >> 16) & 0xF), m = ((tr >> 12) & 7) * 10 + ((tr >> 8) & 0xF);
  unsigned s = ((tr >> 4) & 7) * 10 + (tr & 0xF);
  return h * 3600u + m * 60u + s;
}
