// HTTP through the SIM7080's own client (AT Command Manual V1.05 §13.2): SHCONF URL/BODYLEN/HEADERLEN, SHCONN,
// SHCHEAD + SHAHEAD, SHBOD, SHREQ (reply "+SHREQ: <type>,<status>,<len>"), SHREAD, SHDISC. All NO_SAVE.
// SHBOD: the manual's test response allows only <len_body> = 0 ("length from the input"), text ended by Ctrl-Z;
// it doesn't say whether a ">" prompt comes first, so the code waits briefly for one and prints what it sees.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config.h"
#include "console.h"
#include "hw.h"
#include "i2c.h"
#include "modem.h"
#include "report.h"
#include "tusb.h"

static int at(const char *fmt, const char *arg, unsigned timeout_ms) {
  char cmd[128];
  snprintf(cmd, sizeof cmd, fmt, arg);
  return modem_at(cmd, timeout_ms, true);
}

int http_post(const char *path, const char *body, char *reply, size_t replylen) {
  if (!cfg.url[0]) { cputs("  no server URL: \"cfg url http://host:port\"\n"); return -1; }
  int status = -1;
  char buf[64];
  reply[0] = 0;
  at("AT+SHCONF=\"URL\",\"%s\"", cfg.url, 2000);
  modem_at("AT+SHCONF=\"BODYLEN\",1024", 1000, true);
  modem_at("AT+SHCONF=\"HEADERLEN\",350", 1000, true);
  if (modem_at("AT+SHCONN", 30000, true) != 0) { cputs("  HTTP connect failed (server down? port not forwarded?)\n"); return -1; }
  modem_at("AT+SHCHEAD", 1000, true);
  modem_at("AT+SHAHEAD=\"Content-Type\",\"application/json\"", 1000, true);
  modem_at("AT+SHAHEAD=\"User-Agent\",\"treeweather-bringup\"", 1000, true);
  if (cfg.token[0]) at("AT+SHAHEAD=\"X-Token\",\"%s\"", cfg.token, 1000);

  while (modem_getc() >= 0) {}
  modem_write("AT+SHBOD=0,10000\r", 17);                          // body: length from the input, Ctrl-Z ends it
  uint32_t t0 = millis();
  bool prompt = false;
  while (millis() - t0 < 2000 && !prompt) { int c = modem_getc(); if (c == '>') prompt = true; else if (c < 0) system_poll(); }
  if (!prompt) cputs("  (no \">\" prompt after AT+SHBOD; sending the body anyway)\n");
  modem_write(body, strlen(body));
  modem_write("\x1A", 1);
  if (modem_wait_line("OK", NULL, 0, 12000) < 0) { cputs("  body not accepted\n"); goto disc; }

  char cmd[96];
  snprintf(cmd, sizeof cmd, "AT+SHREQ=\"%s\",3", path);                        // 3 = POST
  if (modem_at(cmd, 5000, true) != 0) { cputs("  request refused\n"); goto disc; }
  char urc[64];
  if (modem_wait_line("+SHREQ:", urc, sizeof urc, 65000) < 0) { cputs("  no response in 65 s\n"); goto disc; }
  const char *c1 = strchr(urc, ','), *c2 = c1 ? strchr(c1 + 1, ',') : NULL;  // +SHREQ: "POST",<status>,<len>
  status = c1 ? atoi(c1 + 1) : -1;
  int len = c2 ? atoi(c2 + 1) : 0;
  if (len > 0) {
    if ((size_t)len >= replylen) len = (int)replylen - 1;
    while (modem_getc() >= 0) {}
    snprintf(cmd, sizeof cmd, "AT+SHREAD=0,%d\r", len);
    modem_write(cmd, strlen(cmd));
    if (modem_wait_line("+SHREAD:", buf, sizeof buf, 5000) >= 0) {       // "+SHREAD: <n>" then <n> raw bytes
      size_t got = modem_read_raw(reply, (size_t)len, 5000);
      reply[got] = 0;
    }
    modem_wait_line("OK", NULL, 0, 2000);
  }
disc:
  modem_at("AT+SHDISC", 5000, true);
  return status;
}

// ---------------------------------------------------------------- one report
static unsigned seq;

static int registration(void) {
  char cereg[48];
  modem_query("AT+CEREG?", "+CEREG:", cereg, sizeof cereg, 1000);
  const char *comma = strchr(cereg, ',');
  return comma ? atoi(comma + 1) : -1;
}

// +CPSI: LTE CAT-M1,Online,310-260,0x7D7F,15453206,235,EUTRAN-BAND12,5035,2,2,<rsrq>,<rsrp>,<rssi>,<rssnr>  (§5.2.19)
static void cpsi_fields(const char *s, char *plmn, size_t plen, int *band, int *rsrq, int *rsrp, int *rssi, int *sinr) {
  const char *f[16]; int n = 0;
  const char *p = strchr(s, ':');
  if (!p) return;
  f[n++] = p + 2;
  for (p = f[0]; *p && n < 16; p++) if (*p == ',') f[n++] = p + 1;
  if (n < 14 || strncmp(f[0], "LTE", 3)) return;
  size_t l = (size_t)(f[3] - f[2] - 1); if (l >= plen) l = plen - 1;
  memcpy(plmn, f[2], l); plmn[l] = 0;
  const char *b = strstr(f[6], "BAND"); *band = b ? atoi(b + 4) : 0;
  *rsrq = atoi(f[10]); *rsrp = atoi(f[11]); *rssi = atoi(f[12]); *sinr = 2 * atoi(f[13]) - 20;   // SINR = 2*RSSNR-20
}

static int json_int(const char *s, const char *key, int dflt) {
  char k[32]; snprintf(k, sizeof k, "\"%s\":", key);
  const char *p = strstr(s, k);
  return p ? atoi(p + strlen(k)) : dflt;
}

bool report_cycle(bool power_off_after) {
  uint32_t t_start = millis();
  bool was_on = modem_status();
  if (!was_on) {
    cputs("report: modem on\n");
    if (modem_power_on() < 0 || !modem_sync(10)) { cputs("report: modem did not start\n"); modem_kill(); return false; }
    modem_at("ATE0", 1000, false); modem_at("AT+CMEE=2", 1000, false);
  }
  cputs("report: waiting for registration (up to 180 s)\n");
  int reg = -1;
  uint32_t t0 = millis();
  while (millis() - t0 < 180000) { reg = registration(); if (reg == 1 || reg == 5) break; delay_ms(2000); }
  uint32_t reg_ms = millis() - t0;
  bool ok = false;
  if (reg != 1 && reg != 5) { cprintf("report: not registered (CEREG %d)\n", reg); goto off; }

  // measurements: everything in one JSON object (integers only: no printf float support needed)
  char csq[48] = "", cpsi[160] = "", imei[32] = "", plmn[12] = "";
  int rssi_csq = 99, band = 0, rsrq = 0, rsrp = 0, rssi = 0, sinr = 0;
  modem_query("AT+CSQ", "+CSQ:", csq, sizeof csq, 1000);
  if (csq[0]) rssi_csq = atoi(csq + 6);
  modem_query("AT+CPSI?", "+CPSI:", cpsi, sizeof cpsi, 2000);
  cpsi_fields(cpsi, plmn, sizeof plmn, &band, &rsrq, &rsrp, &rssi, &sinr);
  modem_query("AT+GSN", "8", imei, sizeof imei, 1000);       // IMEIs start with a digit; 86... for this module
  i2c_init(1);
  uint16_t vcell = 0, soc = 0;
  bool fg = i2c_read_reg16(1, MAX17048_ADDR, 0x02, &vcell) == I2C_OK && i2c_read_reg16(1, MAX17048_ADDR, 0x04, &soc) == I2C_OK;
  uint32_t uid[3]; hw_uid(uid);

  char body[640];
  snprintf(body, sizeof body,
    "{\"id\":\"%08lX%08lX%08lX\",\"imei\":\"%s\",\"fw\":\"bringup\",\"seq\":%u,\"uptime_s\":%lu,\"reset\":\"%s\","
    "\"usb\":%s,\"vdda_mv\":%u,\"fg\":%s,\"vcell_mv\":%lu,\"soc_pct_x100\":%u,\"alrt\":%d,\"sim\":%d,"
    "\"csq\":%d,\"plmn\":\"%s\",\"band\":%d,\"rsrp\":%d,\"rsrq\":%d,\"rssi\":%d,\"sinr\":%d,\"reg_ms\":%lu,\"interval_s\":%lu}",
    uid[0], uid[1], uid[2], imei, seq, millis() / 1000, hw_reset_cause(),
    tud_mounted() ? "true" : "false", hw_vdda_mv(), fg ? "true" : "false",
    fg ? (unsigned long)vcell * 78125u / 1000000u : 0ul, fg ? (unsigned)(soc * 100u / 256u) : 0u,
    pin_read(BAT_ALRT) ? 0 : 1, pin_read(SIM_DET), rssi_csq, plmn, band, rsrp, rsrq, rssi, sinr, reg_ms, cfg.interval_s);
  cprintf("report: %s\n", body);

  // data session, POST, reply
  {
    char urc[48];
    if (modem_query("AT+CNACT=0,1", "+APP PDP:", urc, sizeof urc, 5000) != 0) { cputs("report: data session refused\n"); goto off; }
    if (!urc[0] && modem_wait_line("+APP PDP:", urc, sizeof urc, 60000) < 0) { cputs("report: no data session\n"); goto off; }
    if (strstr(urc, "DEACTIVE")) { cputs("report: data session refused by the network\n"); goto off; }
    char reply[512];
    int status = http_post("/report", body, reply, sizeof reply);
    cprintf("report: HTTP %d, reply %s\n", status, reply[0] ? reply : "(empty)");
    ok = status == 200;
    seq++;
    if (ok) {                                                   // commands from the server ride on the reply
      int iv = json_int(reply, "interval_s", 0);
      if (iv >= 60 && (uint32_t)iv != cfg.interval_s) { cfg.interval_s = (uint32_t)iv; config_save(); cprintf("report: interval now %d s\n", iv); }
    }
    modem_query("AT+CNACT=0,0", "+APP PDP:", urc, sizeof urc, 5000);
  }
off:
  if (power_off_after && !was_on) {
    if (modem_power_off() < 0) { cputs("report: modem would not power down, cutting the rail\n"); modem_kill(); }
  }
  cprintf("report: %s in %lu s\n", ok ? "done" : "FAILED", (millis() - t_start) / 1000);
  return ok;
}

void field_mode(void) {
  cprintf("field mode: a report every %lu s to %s. Any key (or plugging USB in) stops it.\n", cfg.interval_s, cfg.url);
  bool usb_at_start = tud_mounted();
  for (;;) {
    report_cycle(true);
    uint32_t t0 = millis();
    while (millis() - t0 < cfg.interval_s * 1000u) {
      system_poll();
      if (console_getc() >= 0 || (!usb_at_start && tud_mounted())) { cputs("field mode stopped\n"); return; }
    }
  }
}
