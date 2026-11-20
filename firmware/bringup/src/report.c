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

// DNS (manual §19.2): AT+CDNSCFG? lists the servers (0.0.0.0 = none); AT+CDNSGIP="<host>",<retries>,<ms> answers OK,
// then "+CDNSGIP: 1,<host>,<ip>" or "+CDNSGIP: 0,<err>" (4 no server, 5 timeout, 6 no config).
bool dns_check(const char *host) {
  char cmd[96], urc[96];
  modem_at("AT+CDNSCFG?", 2000, true);
  snprintf(cmd, sizeof cmd, "AT+CDNSGIP=\"%s\",2,5000", host);
  urc[0] = 0;
  if (modem_query(cmd, "+CDNSGIP:", urc, sizeof urc, 3000) != 0) { cputs("  DNS lookup refused\n"); return false; }
  if (!urc[0] && modem_wait_line("+CDNSGIP:", urc, sizeof urc, 20000) < 0) { cputs("  no DNS answer in 20 s\n"); return false; }
  cprintf("  %s\n", urc);
  return !strncmp(urc, "+CDNSGIP: 1", 11);
}

static void url_host(char *host, size_t n) {                     // "http://name:port" -> "name"
  const char *p = strstr(cfg.url, "://"); p = p ? p + 3 : cfg.url;
  size_t k = 0;
  while (p[k] && p[k] != ':' && p[k] != '/' && k < n - 1) { host[k] = p[k]; k++; }
  host[k] = 0;
}

int http_post(const char *path, const char *body, char *reply, size_t replylen) {
  if (!cfg.url[0]) { cputs("  no server URL: \"cfg url http://host:port\"\n"); return -1; }
  int status = -1;
  char buf[64];
  reply[0] = 0;
  at("AT+SHCONF=\"URL\",\"%s\"", cfg.url, 2000);
  modem_at("AT+SHCONF=\"BODYLEN\",1024", 1000, true);
  modem_at("AT+SHCONF=\"HEADERLEN\",350", 1000, true);
  if (modem_at("AT+SHCONN", 30000, true) != 0) {
    char host[64]; url_host(host, sizeof host);
    cputs("  HTTP connect failed. Modem HTTP settings, then a DNS check of the server name:\n");
    modem_at("AT+SHCONF?", 2000, true);
    modem_at("AT+SHSTATE?", 1000, true);
    dns_check(host);
    return -1;
  }
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

// ---------------------------------------------------------------- fuel gauge (MAX17048, register map from memory)
// VCELL 0x02 (78.125 uV/LSB), SOC 0x04 (1/256 %), HIBRT 0x0A, CRATE 0x16 (signed, 0.208 %/h per LSB).
// In hibernate the gauge samples VCELL only every 45 s, so a reading can be the voltage from up to 45 s earlier:
// before the modem came on, or during it. HIBRT = 0x0000 keeps it active (a fresh sample every 250 ms, ~20 uA more).
// The write only happens if HIBRT reads its power-on default 0x8030, which also checks the register address.
static int hibrt_seen = -1;                                     // HIBRT as first read since MCU reset (-1 = no gauge)

static int cell_mv(void) {                                     // -1 = no gauge
  uint16_t v;
  i2c_init(1);
  return i2c_read_reg16(1, MAX17048_ADDR, 0x02, &v) == I2C_OK ? (int)((uint32_t)v * 78125u / 1000000u) : -1;
}

static void fg_stay_active(void) {
  uint16_t h;
  i2c_init(1);
  if (i2c_read_reg16(1, MAX17048_ADDR, 0x0A, &h) != I2C_OK) return;
  if (hibrt_seen < 0) hibrt_seen = h;
  if (h == 0x8030) {
    const uint8_t w[3] = { 0x0A, 0x00, 0x00 };
    i2c_xfer(1, MAX17048_ADDR, w, 3, NULL, 0);
    delay_ms(600);                                              // a couple of fresh 250 ms samples
  }
}

// AT+CENG? serving cell (manual §5.2.30), quotes stripped: "earfcn,pci,rsrp,rssi,rsrq,sinr,tac,cellid,mcc,mnc,txpower"
// txpower is in 0.1 dBm and only meaningful while the modem is transmitting.
static void ceng_serving(char *out, size_t n, int *tx) {
  char line[96] = "";
  out[0] = 0; *tx = -999;
  modem_query("AT+CENG?", "+CENG: 0,\"", line, sizeof line, 2000);
  const char *q = strchr(line, '"');
  if (!q) return;
  size_t k = 0;
  for (q++; *q && *q != '"' && k < n - 1; q++) out[k++] = *q;
  out[k] = 0;
  const char *last = strrchr(out, ',');
  if (last && last[1]) *tx = atoi(last + 1);
}

static int json_int(const char *s, const char *key, int dflt) {
  char k[32]; snprintf(k, sizeof k, "\"%s\":", key);
  const char *p = strstr(s, k);
  return p ? atoi(p + strlen(k)) : dflt;
}

// Measured at the end of a cycle, after its report had gone: sent with the next one (-1 = none yet).
static int prev_post_mv = -1, prev_off_mv = -1, prev_post_tx = -999;
static long prev_cycle_ms = -1;

bool report_cycle(bool power_off_after) {
  uint32_t t_start = millis();
  fg_stay_active();
  int pre_mv = cell_mv();                                       // at rest (or with the modem already on)
  bool was_on = modem_status();
  if (!was_on) {
    cputs("report: modem on\n");
    if (modem_power_on() < 0 || !modem_sync(10)) { cputs("report: modem did not start\n"); modem_kill(); return false; }
    modem_at("ATE0", 1000, false); modem_at("AT+CMEE=2", 1000, false);
  }
  uint32_t on_ms = millis() - t_start;
  cputs("report: waiting for registration (up to 180 s)\n");
  int reg = -1;
  uint32_t t0 = millis();
  while (millis() - t0 < 180000) { reg = registration(); if (reg == 1 || reg == 5) break; delay_ms(200); }
  uint32_t reg_ms = millis() - t0;
  bool ok = false;
  int post_mv = -1, post_tx = -999;
  if (reg != 1 && reg != 5) { cprintf("report: not registered (CEREG %d)\n", reg); goto off; }

  // measurements: everything in one JSON object (integers only: no printf float support needed)
  int reg_mv = cell_mv();                                       // just registered: the attach signalling has just happened
  char csq[48] = "", cpsi[160] = "", imei[32] = "", plmn[12] = "", ceng[64];
  int rssi_csq = 99, band = 0, rsrq = 0, rsrp = 0, rssi = 0, sinr = 0, reg_tx;
  uint32_t t1 = millis();                                       // right after registering CSQ can still be 99 and CPSI
  do {                                                          // empty: wait up to 5 s for a measurement
    modem_query("AT+CSQ", "+CSQ:", csq, sizeof csq, 1000);
    rssi_csq = csq[0] ? atoi(csq + 6) : 99;
    if (rssi_csq != 99) break;
    delay_ms(500);
  } while (millis() - t1 < 5000);
  uint32_t meas_ms = millis() - t1;
  modem_query("AT+CPSI?", "+CPSI:", cpsi, sizeof cpsi, 2000);
  cpsi_fields(cpsi, plmn, sizeof plmn, &band, &rsrq, &rsrp, &rssi, &sinr);
  modem_at("AT+CENG=1", 1000, false);
  ceng_serving(ceng, sizeof ceng, &reg_tx);
  modem_query("AT+GSN", "8", imei, sizeof imei, 1000);       // IMEIs start with a digit; 86... for this module
  i2c_init(1);
  uint16_t vcell = 0, soc = 0, crate = 0;
  bool fg = i2c_read_reg16(1, MAX17048_ADDR, 0x02, &vcell) == I2C_OK && i2c_read_reg16(1, MAX17048_ADDR, 0x04, &soc) == I2C_OK;
  if (fg) i2c_read_reg16(1, MAX17048_ADDR, 0x16, &crate);
  uint32_t uid[3]; hw_uid(uid);

  char body[900];
  int n = snprintf(body, sizeof body,
    "{\"id\":\"%08lX%08lX%08lX\",\"imei\":\"%s\",\"fw\":\"bringup-2\",\"seq\":%u,\"uptime_s\":%lu,\"reset\":\"%s\","
    "\"usb\":%s,\"vdda_mv\":%u,\"fg\":%s,\"vcell_mv\":%lu,\"soc_pct_x100\":%u,\"alrt\":%d,\"sim\":%d,"
    "\"csq\":%d,\"plmn\":\"%s\",\"band\":%d,\"rsrp\":%d,\"rsrq\":%d,\"rssi\":%d,\"sinr\":%d,\"reg_ms\":%lu,\"interval_s\":%lu,",
    uid[0], uid[1], uid[2], imei, seq, millis() / 1000, hw_reset_cause(),
    tud_mounted() ? "true" : "false", hw_vdda_mv(), fg ? "true" : "false",
    fg ? (unsigned long)vcell * 78125u / 1000000u : 0ul, fg ? (unsigned)(soc * 100u / 256u) : 0u,
    pin_read(BAT_ALRT) ? 0 : 1, pin_read(SIM_DET), rssi_csq, plmn, band, rsrp, rsrq, rssi, sinr, reg_ms, cfg.interval_s);
  snprintf(body + n, sizeof body - (size_t)n,
    "\"hibrt\":%d,\"crate_raw\":%d,\"pre_mv\":%d,\"reg_mv\":%d,\"on_ms\":%lu,\"meas_ms\":%lu,\"ceng\":\"%s\",\"reg_tx\":%d,"
    "\"prev_post_mv\":%d,\"prev_post_tx\":%d,\"prev_off_mv\":%d,\"prev_cycle_ms\":%ld}",
    hibrt_seen, (int16_t)crate, pre_mv, reg_mv, on_ms, meas_ms, ceng, reg_tx,
    prev_post_mv, prev_post_tx, prev_off_mv, prev_cycle_ms);
  cputs("report: "); cputs(body); cputs("\n");               // cputs: no 256-byte cprintf limit

  // data session, POST, reply
  {
    char urc[48], st[48];
    modem_query("AT+CNACT?", "+CNACT: 0,", st, sizeof st, 2000);      // "+CNACT: 0,<status>,<ip>": 1 = already active
    bool was_active = !strncmp(st, "+CNACT: 0,1", 11);
    if (!was_active) {
      if (modem_query("AT+CNACT=0,1", "+APP PDP:", urc, sizeof urc, 5000) != 0) { cputs("report: data session refused\n"); goto off; }
      if (!urc[0] && modem_wait_line("+APP PDP:", urc, sizeof urc, 60000) < 0) { cputs("report: no data session\n"); goto off; }
      if (strstr(urc, "DEACTIVE")) { cputs("report: data session refused by the network\n"); goto off; }
    }
    char reply[512];
    int status = http_post("/report", body, reply, sizeof reply);
    cprintf("report: HTTP %d, reply %s\n", status, reply[0] ? reply : "(empty)");
    ok = status == 200;
    seq++;
    if (ok) {                                                   // commands from the server ride on the reply
      int iv = json_int(reply, "interval_s", 0);
      if (iv >= 60 && (uint32_t)iv != cfg.interval_s) { cfg.interval_s = (uint32_t)iv; config_save(); cprintf("report: interval now %d s\n", iv); }
    }
    post_mv = cell_mv();                                        // straight after the upload, data session still up
    { char c[64]; ceng_serving(c, sizeof c, &post_tx); }
    if (!was_active) modem_query("AT+CNACT=0,0", "+APP PDP:", urc, sizeof urc, 5000);   // leave it as we found it
  }
off:
  if (power_off_after && !was_on) {
    if (modem_power_off() < 0) { cputs("report: modem would not power down, cutting the rail\n"); modem_kill(); }
    delay_ms(1000);
    prev_off_mv = cell_mv();                                    // modem rail off again
  } else prev_off_mv = -1;
  prev_post_mv = post_mv; prev_post_tx = post_tx;
  prev_cycle_ms = (long)(millis() - t_start);
  cprintf("report: %s in %lu s (cell %d mV before, %d after the upload, %d with the modem off)\n", ok ? "done" : "FAILED",
          (millis() - t_start) / 1000, pre_mv, post_mv, prev_off_mv);
  return ok;
}

bool field_active;

void field_mode(void) {
  cprintf("field mode: a report every %lu s to %s, watchdog on, no uploads below %d mV.\n"
          "Any key (or plugging USB in) stops it.\n", cfg.interval_s, cfg.url, FIELD_MIN_MV);
  bool usb_at_start = tud_mounted();
  hw_watchdog_start();                                          // a hang now ends in a reset, then field mode again
  field_active = true;
  for (;;) {
    int mv = cell_mv();
    if (mv >= 0 && mv < FIELD_MIN_MV && !tud_mounted())
      cprintf("field: cell %d mV is below %d mV: skipping this upload\n", mv, FIELD_MIN_MV);
    else
      report_cycle(true);
    uint32_t t0 = millis();
    while (millis() - t0 < cfg.interval_s * 1000u) {
      system_poll();
      if (console_getc() >= 0 || (!usb_at_start && tud_mounted())) {
        field_active = false;
        cputs("field mode stopped (the watchdog keeps running until the next reset)\n");
        return;
      }
    }
  }
}
