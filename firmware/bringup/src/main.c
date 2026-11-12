// TreeWeather LTE board bring-up firmware: a command console on the USB serial port (and the J4 debug UART).
// Type "help". Every command does one hardware check, so a fault points at a block of the schematic.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "console.h"
#include "hw.h"
#include "i2c.h"
#include "modem.h"
#include "tusb.h"

#define FW_VERSION "bringup 0.1"

void USB_IRQHandler(void) { tud_int_handler(0); }

static bool heartbeat = true;

void system_poll(void) {
  tud_task();
  static uint32_t last;
  if (heartbeat && millis() - last >= 1000) last = millis();
  if (heartbeat) pin_write(LED_USER, millis() - last < 60);     // 60 ms flash every second
}

// ---------------------------------------------------------------- helpers
static int arg_int(const char *s, int dflt) { return (s && *s) ? atoi(s) : dflt; }

static bool report(const char *what, bool ok, const char *detail) {
  cprintf("  %-34s %s  %s\n", what, ok ? "PASS" : "FAIL", detail ? detail : "");
  return ok;
}

// ---------------------------------------------------------------- commands
static void cmd_help(char *a);

static void cmd_info(char *a) {
  uint32_t u[3]; hw_uid(u);
  cprintf("%s, built %s %s\n", FW_VERSION, __DATE__, __TIME__);
  cprintf("MCU: STM32L072, %u KB flash, UID %08lX%08lX%08lX\n", hw_flash_kb(), u[0], u[1], u[2]);
  cprintf("reset cause: %s (RCC_CSR 0x%08lX)\n", hw_reset_cause(), hw_reset_flags());
  cprintf("uptime %lu ms, core 16 MHz (HSI16), USB on HSI48 + CRS\n", millis());
}

static void cmd_vdda(char *a) {
  unsigned mv = hw_vdda_mv();
  cprintf("VDDA (+3V3 rail, LDO U3) = %u.%03u V\n", mv / 1000, mv % 1000);
}

static void cmd_pins(char *a) {
  cprintf("modem: rail %s, PWRKEY %s, STATUS %d, DCD %d, RI %d, CTS %d, RXD %d\n",
          modem_rail_on() ? "ON" : "off", pin_out_level(MDM_PWRKEY) ? "PRESSED" : "released",
          pin_read(MDM_STATUS), pin_read(MDM_DCD), pin_read(MDM_RI), pin_read(MDM_CTS), pin_read(MDM_RXD));
  cprintf("SIM_DET %d (%s), BAT_ALRT %d (%s), GNSS_ANT_EN %d, GNSS_ANT_FLT %d (%s)\n",
          pin_read(SIM_DET), pin_read(SIM_DET) ? "card present" : "no card",
          pin_read(BAT_ALRT), pin_read(BAT_ALRT) ? "no alert" : "ALERT",
          pin_out_level(GNSS_ANT_EN), pin_read(GNSS_ANT_FLT), pin_read(GNSS_ANT_FLT) ? "ok" : "OVER-CURRENT");
}

static void cmd_led(char *a) {
  if (a && !strcmp(a, "on"))       { heartbeat = false; pin_write(LED_USER, 1); }
  else if (a && !strcmp(a, "off")) { heartbeat = false; pin_write(LED_USER, 0); }
  else                             { heartbeat = true; }
  cprintf("LED_USER (D2): %s\n", heartbeat ? "heartbeat" : pin_out_level(LED_USER) ? "on" : "off");
}

static void cmd_lse(char *a) {
  int drive = arg_int(a, 3);
  cprintf("starting LSE (Y1, 32.768 kHz) at drive %d (0 low .. 3 high)...\n", drive);
  int ms = hw_lse_start((unsigned)drive, 5000);
  if (ms < 0) cputs("LSE did NOT start in 5 s: check Y1, C54/C55, the PC14/PC15 traces\n");
  else        cprintf("LSE ready after %d ms\n", ms);
}

static void cmd_rtc(char *a) {
  if (!hw_lse_ready() && hw_lse_start(3, 5000) < 0) { cputs("LSE not running: see \"lse\"\n"); return; }
  int secs = arg_int(a, 10);
  hw_rtc_start();
  uint32_t t0 = millis();
  cprintf("RTC on LSE vs the HSI16 tick for %d s (HSI16 is only +-1 %%: this checks the RTC runs, not ppm)...\n", secs);
  while (hw_rtc_seconds() < (uint32_t)secs) system_poll();
  cprintf("RTC counted %d s in %lu ms of HSI16 time\n", secs, millis() - t0);
}

static void cmd_i2c(char *a) {
  int only = arg_int(a, 0);
  for (int b = 1; b <= 3; b++) {
    if (only && b != only) continue;
    bool scl, sda;
    i2c_lines(b, &scl, &sda);
    cprintf("%s: idle SCL=%d SDA=%d%s\n", i2c_name(b), scl, sda,
            (scl && sda) ? "" : "  <- a line is held LOW: missing pull-up, short, or a hung device");
    if (scl && !sda) cprintf("  bus recovery: SDA %s\n", i2c_recover(b) ? "released" : "still low");
    if (!scl) continue;
    i2c_init(b);
    int found = 0;
    for (int addr = 0x08; addr < 0x78; addr++)
      if (i2c_probe(b, (uint8_t)addr)) { cprintf("  device at 0x%02X%s\n", addr, addr == MAX17048_ADDR && b == 1 ? " (MAX17048)" : ""); found++; }
    if (!found) cputs("  no devices\n");
  }
}

// MAX17048 register map and scaling as remembered (VCELL 0x02, 78.125 uV/LSB; SOC 0x04, 1/256 %; VERSION 0x08;
// CONFIG 0x0C; CRATE 0x16, 0.208 %/h/LSB): NOT yet checked against the datasheet (19-6171 Rev 7).
static void cmd_fg(char *a) {
  i2c_init(1);
  uint16_t ver, vcell, soc, cfg, crate;
  if (i2c_read_reg16(1, MAX17048_ADDR, 0x08, &ver) != I2C_OK) { cputs("MAX17048 does not answer at 0x36 on I2C1\n"); return; }
  i2c_read_reg16(1, MAX17048_ADDR, 0x02, &vcell);
  i2c_read_reg16(1, MAX17048_ADDR, 0x04, &soc);
  i2c_read_reg16(1, MAX17048_ADDR, 0x0C, &cfg);
  i2c_read_reg16(1, MAX17048_ADDR, 0x16, &crate);
  uint32_t uv = (uint32_t)vcell * 78125u / 1000u;
  cprintf("MAX17048: VERSION 0x%04X, CONFIG 0x%04X\n", ver, cfg);
  cprintf("  VCELL %lu.%03lu V   SOC %u.%02u %%   CRATE %d (x0.208 %%/h)   ALRT pin %s\n",
          uv / 1000000u, (uv / 1000u) % 1000u, soc >> 8, (unsigned)((soc & 0xFF) * 100u / 256u),
          (int16_t)crate, pin_read(BAT_ALRT) ? "high" : "LOW (alert)");
}

static void cmd_gnss(char *a) {
  if (a && !strcmp(a, "on"))  pin_write(GNSS_ANT_EN, 1);
  if (a && !strcmp(a, "off")) pin_write(GNSS_ANT_EN, 0);
  delay_ms(20);
  cprintf("GNSS antenna feed (U10): %s, OC flag %s\n", pin_out_level(GNSS_ANT_EN) ? "ON (3.3 V on J7)" : "off",
          pin_read(GNSS_ANT_FLT) ? "ok" : "LOW = over-current (shorted or damaged antenna cable)");
}

// ---- network diagnostics. Read-only: none of these change the modem's stored settings (CNMP, CMNB, CBANDCFG and
// IPR are AUTO_SAVE when written, so writing them is left for a deliberate configuration step). Checked against the
// SIM7070/7080/7090 Series AT Command Manual V1.05: CFUN §3.2, CSQ §3.2, COPS §3.2.9, CNMP §5.2.16, CMNB §5.2.17,
// CPSI §5.2.19, CBANDCFG §5.2.26, CEREG §6.2.7.
static bool modem_ready(void) {
  if (!modem_status()) { cputs("modem is off: \"mdm on\" first\n"); return false; }
  modem_uart_attach();
  return true;
}

static void at_show(const char *cmd, const char *what, unsigned timeout_ms) {
  cprintf("%s (%s):\n", what, cmd);
  int rc = modem_at(cmd, timeout_ms, true);
  if (rc == 1) cputs("  (failed: see the error text above)\n");
  if (rc < 0) cputs("  (no reply)\n");
}

static void mdm_info(void) {
  if (!modem_ready()) return;
  at_show("AT+CGMM", "model", 1000);
  at_show("AT+CGMR", "firmware", 1000);
  at_show("AT+GSN", "IMEI", 1000);
  at_show("AT+CPIN?", "SIM state", 2000);
  at_show("AT+CCID", "SIM ICCID", 2000);
  at_show("AT+CFUN?", "radio (1 = full, 0/4 = off)", 1000);
  at_show("AT+CNMP?", "RAT preference (2 auto, 38 LTE only)", 1000);
  at_show("AT+CMNB?", "LTE flavour (1 Cat-M, 2 NB-IoT, 3 both)", 1000);
  at_show("AT+CBANDCFG?", "enabled bands", 2000);
  at_show("AT+CEREG?", "EPS registration (stat 1 home, 5 roaming, 2 searching, 0 not searching, 3 denied)", 1000);
  at_show("AT+COPS?", "current operator", 2000);
  at_show("AT+CSQ", "signal (rssi 0-31, 99 = unknown)", 1000);
  at_show("AT+CPSI?", "serving cell", 2000);
}

static void mdm_scan(void) {
  if (!modem_ready()) return;
  cputs("operator scan (AT+COPS=?): searches every enabled band and both LTE flavours, 1-3 min...\n"
        "  each entry: (status, long name, short name, MCC+MNC, access tech: 7 = LTE Cat-M, 9 = NB-IoT)\n"
        "  status: 1 available, 2 current, 3 forbidden. No SIM: the scan may still run, or the modem may refuse it.\n");
  uint32_t t0 = millis();
  int rc = modem_at("AT+COPS=?", 240000, true);
  cprintf("  %s after %lu s\n", rc == 0 ? "done" : rc == 1 ? "ERROR" : "timed out", (millis() - t0) / 1000);
}

static void mdm_watch(int period_s) {
  if (!modem_ready()) return;
  if (period_s < 2) period_s = 2;
  cprintf("signal and serving cell every %d s; press any key to stop\n", period_s);
  static const char *const reg[] = { "not searching", "registered (home)", "searching", "denied", "unknown", "registered (roaming)" };
  for (;;) {
    char csq[48], cpsi[160], cereg[48];
    modem_query("AT+CSQ", "+CSQ:", csq, sizeof csq, 1000);
    modem_query("AT+CPSI?", "+CPSI:", cpsi, sizeof cpsi, 2000);
    modem_query("AT+CEREG?", "+CEREG:", cereg, sizeof cereg, 1000);
    int rssi = csq[0] ? atoi(csq + 6) : 99;                       // "+CSQ: <rssi>,<ber>"
    const char *comma = strchr(cereg, ',');
    int stat = comma ? atoi(comma + 1) : 4;                        // "+CEREG: <n>,<stat>"
    cprintf("[%lu s] RSSI ", millis() / 1000);
    if (rssi == 99) cputs("unknown");                              // CSQ: 0 = -115 dBm or less, 31 = -52 dBm or more
    else cprintf("%d dBm (CSQ %d)", rssi == 0 ? -115 : rssi == 1 ? -111 : -114 + 2 * rssi, rssi);
    cprintf(" | %s\n  %s\n", stat >= 0 && stat <= 5 ? reg[stat] : "?", cpsi[0] ? cpsi : "(no +CPSI reply)");
    uint32_t t0 = millis();
    while (millis() - t0 < (uint32_t)period_s * 1000u) {
      system_poll();
      if (console_getc() >= 0) { cputs("stopped\n"); return; }
    }
  }
}

static void cmd_mdm(char *a) {
  if (a && !strcmp(a, "on")) {
    cputs("modem on: rail (PC13), 1.2 s PWRKEY, waiting for STATUS...\n");
    int ms = modem_power_on();
    if (ms < 0) { cputs("STATUS never went high: check the +3V8 rail, Q1/PWRKEY, R27, U5 channel 8. Rail left ON (\"mdm kill\")\n"); return; }
    cprintf("STATUS high after %d ms; syncing AT...\n", ms);
    if (!modem_sync(10)) { cputs("no reply to AT: check U5 (OE = VDD_EXT), TXD/RXD\n"); return; }
    cputs("AT OK: the TXD/RXD path through U5 works\n");
    modem_at("ATE0", 1000, false);                                 // no command echo: replies are easier to read
    modem_at("AT+CMEE=2", 1000, false);                            // verbose "+CME ERROR: <text>" (NO_SAVE, manual §3.2.8)
    cputs("start-up messages for 5 s (+CFUN, +CPIN, SMS Ready...; no \"RDY\" while the modem auto-bauds, manual §1):\n");
    modem_drain(5000);
  } else if (a && !strcmp(a, "info")) {
    mdm_info();
  } else if (a && !strcmp(a, "scan")) {
    mdm_scan();
  } else if (a && !strncmp(a, "watch", 5)) {
    mdm_watch(arg_int(a + 5, 5));
  } else if (a && !strcmp(a, "off")) {
    cputs("modem off: AT+CPOWD=1, waiting for STATUS low...\n");
    int ms = modem_power_off();
    cputs(ms < 0 ? "STATUS stayed high: rail left ON (\"mdm kill\" forces it)\n" : "modem off, rail off\n");
  } else if (a && !strcmp(a, "kill")) {
    modem_kill(); cputs("rail cut (hung-modem recovery only)\n");
  } else if (a && !strncmp(a, "pwrkey", 6)) {
    int ms = arg_int(a + 6, 1200);
    cprintf("PWRKEY pulse %d ms\n", ms); modem_pwrkey_pulse((unsigned)ms);
  } else {
    cprintf("modem: rail %s, STATUS %s, UART %s\n", modem_rail_on() ? "ON" : "off", modem_status() ? "HIGH (on)" : "low (off)",
            modem_uart_attached() ? "attached" : "detached");
  }
}

static void cmd_at(char *a) {
  if (!modem_status()) { cputs("modem is off: \"mdm on\" first\n"); return; }
  modem_uart_attach();
  char cmd[100];
  bool has_at = a && (a[0] == 'A' || a[0] == 'a') && (a[1] == 'T' || a[1] == 't');
  snprintf(cmd, sizeof cmd, "%s%s", has_at ? "" : "AT", a ? a : "");   // "at +CSQ" and "at AT+CSQ" both send AT+CSQ
  cprintf("  > %s\n", cmd);
  int rc = modem_at(cmd, 5000, true);
  if (rc < 0) cputs("  (timeout)\n");
}

static void cmd_bridge(char *a) {
  if (!modem_status()) { cputs("modem is off: \"mdm on\" first\n"); return; }
  modem_uart_attach();
  cputs("console <-> modem UART bridge. Ctrl-] (0x1D) to leave.\n");
  for (;;) {
    tud_task();
    int c;
    while ((c = console_getc()) >= 0) {
      if (c == 0x1D) { cputs("\nbridge closed\n"); return; }
      char ch = (char)c; modem_write(&ch, 1);
    }
    char buf[64]; size_t n = 0;
    while (n < sizeof buf && (c = modem_getc()) >= 0) buf[n++] = (char)c;
    if (n) cwrite_raw(buf, n);
  }
}

static void cmd_selftest(char *a) {
  char d[64];
  int fails = 0;
  cputs("self-test (modem stays off):\n");
  unsigned mv = hw_vdda_mv();
  snprintf(d, sizeof d, "%u mV", mv);
  fails += !report("VDDA / +3V3 rail 3.20-3.40 V", mv >= 3200 && mv <= 3400, d);
  int ms = hw_lse_ready() ? 0 : hw_lse_start(3, 5000);
  snprintf(d, sizeof d, ms < 0 ? "no start in 5 s" : "ready (%d ms)", ms);
  fails += !report("LSE crystal Y1", ms >= 0, d);
  for (int b = 1; b <= 3; b++) {
    bool scl, sda; i2c_lines(b, &scl, &sda);
    snprintf(d, sizeof d, "SCL=%d SDA=%d", scl, sda);
    char what[40]; snprintf(what, sizeof what, "I2C%d pull-ups (lines idle high)", b);
    fails += !report(what, scl && sda, d);
  }
  i2c_init(1);
  bool fg = i2c_probe(1, MAX17048_ADDR);   // U8 runs from VBAT (the cell), not +3V3: no cell on J9 = no ACK
  fails += !report("MAX17048 ACKs at 0x36 on I2C1", fg, fg ? NULL : "U8 is powered by VBAT: is a cell on J9?");
  fails += !report("modem off (STATUS low, R27)", !modem_status(), modem_rail_on() ? "rail is ON" : "rail off");
  fails += !report("GNSS antenna OC flag high", pin_read(GNSS_ANT_FLT), pin_out_level(GNSS_ANT_EN) ? "feed on" : "feed off");
  fails += !report("battery alert (ALRT) inactive", pin_read(BAT_ALRT), "R37 pull-up");
  cprintf("  %-34s %s\n", "SIM card detect", pin_read(SIM_DET) ? "card present" : "no card");
  cprintf("%d failure%s\n", fails, fails == 1 ? "" : "s");
}

static void cmd_dfu(char *a) {
  cputs("rebooting into the ST ROM DFU bootloader (0483:df11). Flash with:  cmake --build build --target flash\n");
  delay_ms(200);
  hw_enter_bootloader();
}

static void cmd_reset(char *a) { cputs("resetting\n"); delay_ms(200); NVIC_SystemReset(); }

static const struct { const char *name; void (*fn)(char *); const char *help; } cmds[] = {
  { "help",     cmd_help,     "this list" },
  { "info",     cmd_info,     "firmware, MCU ID, reset cause" },
  { "selftest", cmd_selftest, "all checks that don't power the modem" },
  { "vdda",     cmd_vdda,     "measure the +3V3 rail (internal reference)" },
  { "pins",     cmd_pins,     "every status input: modem lines, SIM detect, battery alert, GNSS flag" },
  { "led",      cmd_led,      "led on|off|blink  user LED D2" },
  { "lse",      cmd_lse,      "lse [drive 0-3]  start the 32.768 kHz crystal, time it" },
  { "rtc",      cmd_rtc,      "rtc [seconds]  run the RTC on the LSE against the system tick" },
  { "i2c",      cmd_i2c,      "i2c [1|2|3]  check the pull-ups and scan for devices" },
  { "fg",       cmd_fg,       "read the MAX17048 fuel gauge (cell voltage, state of charge)" },
  { "gnss",     cmd_gnss,     "gnss on|off  antenna feed (U10) and its over-current flag" },
  { "mdm",      cmd_mdm,      "mdm on|off|kill|pwrkey [ms]  modem power sequence and status\n"
                              "            mdm info | scan | watch [s]  identity and config, operator scan, live signal" },
  { "at",       cmd_at,       "at <command>  one AT command, e.g. \"at +CPIN?\" or \"at +CSQ\"" },
  { "bridge",   cmd_bridge,   "pass the console straight through to the modem UART (Ctrl-] exits)" },
  { "dfu",      cmd_dfu,      "reboot into the ROM USB bootloader for flashing" },
  { "reset",    cmd_reset,    "software reset" },
};

static void cmd_help(char *a) {
  for (unsigned i = 0; i < sizeof cmds / sizeof cmds[0]; i++) cprintf("  %-9s %s\n", cmds[i].name, cmds[i].help);
}

static void dispatch(char *line) {
  while (*line == ' ') line++;
  if (!*line) return;
  char *arg = strchr(line, ' ');
  if (arg) { *arg++ = 0; while (*arg == ' ') arg++; }
  for (unsigned i = 0; i < sizeof cmds / sizeof cmds[0]; i++)
    if (!strcmp(line, cmds[i].name)) { cmds[i].fn(arg); return; }
  cprintf("unknown command \"%s\" (try \"help\")\n", line);
}

int main(void) {
  hw_early();
  hw_init();
  console_init();
  tusb_rhport_init_t init = { .role = TUSB_ROLE_DEVICE, .speed = TUSB_SPEED_AUTO };
  tusb_init(0, &init);

  bool was_connected = false;
  for (;;) {
    system_poll();
    bool c = console_usb_connected();
    if (c && !was_connected) {                                    // a terminal just opened the port
      delay_ms(50);
      cprintf("\nTreeWeather LTE board, %s. Reset cause: %s. Type \"help\".\n> ", FW_VERSION, hw_reset_cause());
    }
    was_connected = c;
    const char *line = console_readline();
    if (line) {
      char buf[96]; strncpy(buf, line, sizeof buf - 1); buf[sizeof buf - 1] = 0;
      dispatch(buf);
      cputs("> ");
    }
  }
}
