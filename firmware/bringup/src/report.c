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
#include "sensors.h"
#include "store.h"
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
  modem_at("AT+SHCONF=\"BODYLEN\",4096", 1000, true);   // the most it takes (manual §13.2.1)
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

// ---------------------------------------------------------------- modem and fuel-gauge readouts
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

static void fg_allow_hibernate(void) {                         // back to the default between check-ins (~20 uA less)
  uint16_t h;
  i2c_init(1);
  if (i2c_read_reg16(1, MAX17048_ADDR, 0x0A, &h) == I2C_OK && h == 0x0000) {
    const uint8_t w[3] = { 0x0A, 0x80, 0x30 };
    i2c_xfer(1, MAX17048_ADDR, w, 3, NULL, 0);
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

// ---------------------------------------------------------------- one upload session
// Modem on, register (90 s cap), then POSTs of up to REC_PER_POST stored records each, until the server has them all
// (or MAX_POSTS). Each POST carries a status block too. The reply's "ack" is the last record the server saved.
#define REG_TIMEOUT_MS 90000
#define REC_PER_POST   16            // ~110 bytes each in JSON: a POST stays under ~3 KB (BODYLEN max 4096)
#define MAX_POSTS      9             // a full ring (133 records) in one session

// Measured at the end of a session, after its last POST: sent with the next one (-1 = none yet).
static int prev_post_mv = -1, prev_off_mv = -1;
static long prev_cycle_ms = -1;
static char body[3400];

static const char *const batt_names[] = { "ok", "low", "last", "locked" };

static int dc_str(char *out, size_t n, int dc) {             // 0.1 C as "-1.5" (no float printf)
  if (dc == -9999) return snprintf(out, n, "null");
  return snprintf(out, n, "%s%d.%d", dc < 0 ? "-" : "", (dc < 0 ? -dc : dc) / 10, (dc < 0 ? -dc : dc) % 10);
}


bool upload_session(bool power_off_after, int batt) {
  uint32_t t_start = millis();
  fg_stay_active();
  int pre_mv = cell_mv();                                       // at rest (or with the modem already on)
  bool was_on = modem_status(), ok = false;
  int post_mv = -1, posts = 0;
  cprintf("upload: %lu record(s) waiting, battery %s\n", store_unsent(), batt_names[batt & 3]);
  if (!was_on) {
    cputs("upload: modem on\n");
    if (modem_power_on() < 0 || !modem_sync(10)) { cputs("upload: modem did not start\n"); modem_kill(); goto done; }
    modem_at("ATE0", 1000, false); modem_at("AT+CMEE=2", 1000, false);
  }
  uint32_t on_ms = millis() - t_start;
  {                                                             // no usable SIM: don't sit 90 s waiting to register
    char cpin[32] = "";                                         // (asks the modem, so a bad SIM_DET switch can't block uploads)
    uint32_t tc = millis();
    do { modem_query("AT+CPIN?", "+CPIN:", cpin, sizeof cpin, 1000); if (strstr(cpin, "READY")) break; delay_ms(500); }
    while (millis() - tc < 10000);
    if (!strstr(cpin, "READY")) { cprintf("upload: SIM not ready (%s)\n", cpin[0] ? cpin : "no reply"); goto off; }
  }
  cprintf("upload: waiting for registration (up to %d s)\n", REG_TIMEOUT_MS / 1000);
  int reg = -1;
  uint32_t t0 = millis();
  while (millis() - t0 < REG_TIMEOUT_MS) { reg = registration(); if (reg == 1 || reg == 5) break; delay_ms(200); }
  uint32_t reg_ms = millis() - t0;
  if (reg != 1 && reg != 5) { cprintf("upload: not registered after %lu s (CEREG %d)\n", reg_ms / 1000, reg); goto off; }

  // radio and identity readouts, once per session (integers only: no printf float support)
  int reg_mv = cell_mv();
  char csq[48] = "", cpsi[160] = "", imei[32] = "", plmn[12] = "", ceng[64];
  int rssi_csq = 99, band = 0, rsrq = 0, rsrp = 0, rssi = 0, sinr = 0, reg_tx;
  uint32_t t1 = millis();                                       // right after registering CSQ can still be 99 and CPSI
  do {                                                          // empty: wait up to 5 s for a measurement
    modem_query("AT+CSQ", "+CSQ:", csq, sizeof csq, 1000);
    rssi_csq = csq[0] ? atoi(csq + 6) : 99;
    if (rssi_csq != 99) break;
    delay_ms(500);
  } while (millis() - t1 < 5000);
  modem_query("AT+CPSI?", "+CPSI:", cpsi, sizeof cpsi, 2000);
  cpsi_fields(cpsi, plmn, sizeof plmn, &band, &rsrq, &rsrp, &rssi, &sinr);
  modem_at("AT+CENG=1", 1000, false);
  ceng_serving(ceng, sizeof ceng, &reg_tx);
  modem_query("AT+GSN", "8", imei, sizeof imei, 1000);       // IMEIs start with a digit; 86... for this module
  uint32_t uid[3]; hw_uid(uid);

  char urc[48], st[48];
  modem_query("AT+CNACT?", "+CNACT: 0,", st, sizeof st, 2000);        // "+CNACT: 0,<status>,<ip>": 1 = already active
  bool was_active = !strncmp(st, "+CNACT: 0,1", 11);
  if (!was_active) {
    if (modem_query("AT+CNACT=0,1", "+APP PDP:", urc, sizeof urc, 5000) != 0) { cputs("upload: data session refused\n"); goto off; }
    if (!urc[0] && modem_wait_line("+APP PDP:", urc, sizeof urc, 60000) < 0) { cputs("upload: no data session\n"); goto off; }
    if (strstr(urc, "DEACTIVE")) { cputs("upload: data session refused by the network\n"); goto off; }
  }

  for (;;) {
    uint16_t vcell = 0, soc = 0, crate = 0;
    i2c_init(1);
    bool fg = i2c_read_reg16(1, MAX17048_ADDR, 0x02, &vcell) == I2C_OK && i2c_read_reg16(1, MAX17048_ADDR, 0x04, &soc) == I2C_OK;
    if (fg) i2c_read_reg16(1, MAX17048_ADDR, 0x16, &crate);
    uint32_t ms, now = hw_clock_read(&ms);
    int n = snprintf(body, sizeof body,
      "{\"id\":\"%08lX%08lX%08lX\",\"imei\":\"%s\",\"fw\":\"logger-2\",\"rv\":2,\"ep\":%lu,\"now\":%lu,\"now_ms\":%lu,\"clk\":\"%s\","
      "\"uptime_s\":%lu,\"reset\":\"%s\",\"usb\":%s,\"vdda_mv\":%u,\"vcell_mv\":%lu,\"soc_pct_x100\":%u,\"crate_raw\":%d,"
      "\"batt\":\"%s\",\"backoff\":%u,\"sample_s\":%lu,\"batch\":%lu,\"newest\":%lu,\"acked\":%lu,\"cap\":%u,\"post\":%d,",
      uid[0], uid[1], uid[2], imei, (unsigned long)store_epoch(), (unsigned long)now, (unsigned long)ms,
      hw_clock_init() ? "LSE" : "LSI", millis() / 1000, hw_reset_cause(), tud_mounted() ? "true" : "false", hw_vdda_mv(),
      fg ? (unsigned long)vcell * 78125u / 1000000u : 0ul, fg ? (unsigned)(soc * 100u / 256u) : 0u, (int16_t)crate,
      batt_names[batt & 3], (unsigned)(hw_bkp_read(0) & 0xF), (unsigned long)cfg.sample_s, (unsigned long)cfg.batch,
      (unsigned long)store_newest(), (unsigned long)store_acked(), store_capacity(), posts);
    n += snprintf(body + n, sizeof body - (size_t)n,
      "\"csq\":%d,\"plmn\":\"%s\",\"band\":%d,\"rsrp\":%d,\"rsrq\":%d,\"rssi\":%d,\"sinr\":%d,\"ceng\":\"%s\",\"reg_tx\":%d,"
      "\"reg_ms\":%lu,\"on_ms\":%lu,\"pre_mv\":%d,\"reg_mv\":%d,\"prev_post_mv\":%d,\"prev_off_mv\":%d,\"prev_cycle_ms\":%ld,\"recs\":[",
      rssi_csq, plmn, band, rsrp, rsrq, rssi, sinr, ceng, reg_tx, reg_ms, on_ms, pre_mv, reg_mv,
      prev_post_mv, prev_off_mv, prev_cycle_ms);
    uint32_t first = store_first_unsent(), last = 0;
    int k = 0;
    for (uint32_t q = first; q <= store_newest() && k < REC_PER_POST && (size_t)n + 160 < sizeof body; q++) {
      rec_t r;
      last = q;                                                 // a corrupt slot is skipped, and acked with the rest
      if (!store_get(q, &r)) continue;
      char tc[12];
      dc_str(tc, sizeof tc, r.mcu_dc);
      const sensors_t *v = &r.s;                                // record layout 2: see the server's RECORD_V2
      n += snprintf(body + n, sizeof body - (size_t)n, "%s[%lu,%lu,%u,%s,%u,%u,%d,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u]",
                    k ? "," : "", (unsigned long)r.seq, (unsigned long)r.t, r.vcell_mv, tc, r.flags, v->status,
                    v->aht_t, v->aht_rh, v->als[0], v->white[0], v->als[1], v->white[1],
                    v->uv[0][0], v->uv[0][1], v->uv[0][2], v->uv[1][0], v->uv[1][1], v->uv[1][2], v->as_temp);
      k++;
    }
    n += snprintf(body + n, sizeof body - (size_t)n, "]}");
    if ((size_t)n >= sizeof body) { cputs("upload: body too long\n"); break; }
    cprintf("upload: POST %d, records %lu-%lu (%d), %d bytes\n", posts + 1, (unsigned long)first, (unsigned long)last, k, n);
    char reply[512];
    int status = http_post("/report", body, reply, sizeof reply);
    cprintf("upload: HTTP %d, reply %s\n", status, reply[0] ? reply : "(empty)");
    if (status != 200) break;
    posts++;
    ok = true;
    int ack = json_int(reply, "ack", -1);
    if (last && ack > 0) store_ack((uint32_t)ack < last ? (uint32_t)ack : last);
    int v = json_int(reply, "sample_s", 0);                     // settings from the server ride on the reply
    if (v >= 60 && (uint32_t)v != cfg.sample_s) { cfg.sample_s = (uint32_t)v; config_save(); cprintf("upload: sample_s now %d\n", v); }
    v = json_int(reply, "batch", 0);
    if (v >= 1 && v <= 96 && (uint32_t)v != cfg.batch) { cfg.batch = (uint32_t)v; config_save(); cprintf("upload: batch now %d\n", v); }
    if (!store_unsent() || !last || ack < (int)last || posts >= MAX_POSTS) break;   // done, or the server isn't keeping up
  }
  post_mv = cell_mv();                                          // straight after the last POST, data session still up
  if (!was_active) modem_query("AT+CNACT=0,0", "+APP PDP:", urc, sizeof urc, 5000);   // leave it as we found it
off:
  if (power_off_after && !was_on) {
    if (modem_power_off() < 0) { cputs("upload: modem would not power down, cutting the rail\n"); modem_kill(); }
    delay_ms(1000);
    prev_off_mv = cell_mv();                                    // modem rail off again
  } else prev_off_mv = -1;
done:
  fg_allow_hibernate();
  prev_post_mv = post_mv;
  prev_cycle_ms = (long)(millis() - t_start);
  cprintf("upload: %s, %d POST(s) in %lu s, %lu record(s) still waiting (cell %d mV before, %d after, %d modem off)\n",
          ok ? "done" : "FAILED", posts, (millis() - t_start) / 1000, store_unsent(), pre_mv, post_mv, prev_off_mv);
  return ok;
}

// ---------------------------------------------------------------- sampling
static bool reset_unsampled = true;                             // no sample yet since this MCU reset

// Field-mode state that must survive a watchdog reset: RTC backup registers (cleared only by a power cut).
// BKP0 = 0xF1E1 <<16 | locked-out (bit 8) | back-off level (bits 0-3);  BKP1 = device time of the next retry.
#define FSTATE_MAGIC 0xF1E10000u
static uint32_t fstate(void) { uint32_t v = hw_bkp_read(0); return (v & 0xFFFF0000u) == FSTATE_MAGIC ? v : FSTATE_MAGIC; }
static unsigned backoff_level(void) { return fstate() & 0xFu; }
static bool locked_out(void) { return fstate() & 0x100u; }
static void fstate_set(unsigned level, bool locked) { hw_bkp_write(0, FSTATE_MAGIC | (locked ? 0x100u : 0) | (level & 0xFu)); }
static uint32_t retry_at(void) { return (hw_bkp_read(0) & 0xFFFF0000u) == FSTATE_MAGIC ? hw_bkp_read(1) : 0; }

uint32_t sample_take(void) {
  rec_t r;
  memset(&r, 0, sizeof r);
  r.t = hw_clock_s();
  int mv = cell_mv();
  r.vcell_mv = mv > 0 ? (uint16_t)mv : 0;
  r.mcu_dc = (int16_t)hw_mcu_temp_dc();
  sensors_read(&r.s);
  if (reset_unsampled) r.flags |= REC_BOOT | (hw_clock_fresh() ? REC_CLOCK_NEW : 0);
  if (mv > 0 && mv < BATT_LOW_MV) r.flags |= REC_BATT_LOW;
  if (locked_out()) r.flags |= REC_LOCKED_OUT;
  if (tud_mounted()) r.flags |= REC_USB;
  uint32_t seq = store_append(&r);
  if (seq) reset_unsampled = false;
  char tc[12]; dc_str(tc, sizeof tc, r.mcu_dc);
  if (seq) cprintf("sample %lu: t %lu s, cell %d mV, MCU %s C, flags 0x%02X (%lu waiting)\n", (unsigned long)seq,
                   (unsigned long)r.t, mv, tc, r.flags, store_unsent());
  if (seq) sensors_print(&r.s);
  else cputs("sample: EEPROM write FAILED\n");
  return seq;
}

bool report_now(bool power_off_after) {                       // console "report": no lockout, no back-off
  int mv = cell_mv();
  return upload_session(power_off_after, mv < 0 ? 0 : mv < BATT_STOP_MV ? 2 : mv < BATT_LOW_MV ? 1 : 0);
}

// ---------------------------------------------------------------- field mode
bool field_active;

// After a failed upload, wait 1, 2, then 4 upload periods (sample_s * batch) before trying again: hourly uploads
// back off to 1, 2, 4 h; a fast test schedule retries in minutes. Never more than BACKOFF_MAX_S, unless one
// period is longer than that.
#define BACKOFF_MAX_S 14400u
static uint32_t backoff_s(unsigned lvl) {
  uint32_t period = cfg.sample_s * cfg.batch, w = lvl ? period << (lvl - 1) : 0;
  uint32_t cap = period > BACKOFF_MAX_S ? period : BACKOFF_MAX_S;
  return w > cap ? cap : w;
}

// An upload when enough samples wait, unless a failed one set a retry time. Low cell: below BATT_STOP_MV one last
// upload (batt "last"), whether or not it works, then field_mode() parks the board (park()).
static void field_upload(void) {
  int mv = cell_mv();
  bool locked = false;
  int batt = 0;
  if (mv >= 0 && mv < BATT_STOP_MV) { locked = true; batt = 2; cprintf("field: cell %d mV: last upload, then parked\n", mv); }
  else if (mv >= 0 && mv < BATT_LOW_MV) batt = 1;
  fstate_set(backoff_level(), locked);
  bool ok = upload_session(true, batt);
  unsigned lvl = backoff_level();
  if (ok) lvl = 0; else if (lvl < 3) lvl++;
  fstate_set(lvl, locked);
  uint32_t wait = ok ? 0 : backoff_s(lvl);
  hw_bkp_write(1, ok ? 0 : hw_clock_s() + wait);
  if (!ok) cprintf("field: next upload attempt in %lu s\n", (unsigned long)wait);
}

static bool upload_due(uint32_t now) { return store_unsent() >= cfg.batch && now >= retry_at(); }

// Flat cell: stop everything for good, to keep the cell above the level that damages it (the DW01A only cuts off at
// ~2.5 V). No sampling, no modem, USB off; Stop mode, waking every 10 s only because the IWDG can't be stopped, with
// a 10 ms flash of D2 once a minute so a parked board can be told from a dead one. The sensors are powered down
// between readings and the fuel gauge hibernates on its own at zero load (HIBRT default). Only a reset or a power cut
// (a recharged or new cell) gets out of it; after a reset the lock stays until the cell reads BATT_RESUME_MV.
__attribute__((noreturn)) static void park(void) {
  cprintf("field: parked (cell flat). Recharge or replace the cell, or press RESET with USB for the console.\n");
  console_usb_stop();
  for (unsigned n = 0;; n++) {
    hw_watchdog_kick();
    if (n % 6 == 0) { pin_write(LED_USER, 1); hw_stop_ms(10); pin_write(LED_USER, 0); }
    hw_stop_ms(10000);
  }
}

// Stop mode until the device clock reaches t, in chunks of up to 10 s. The IWDG keeps running in Stop (DS10689
// §3.4 note) and can time out after 19 s with a fast LSI, so each chunk ends with a kick. Each chunk opens with a
// double flash of D2, made by sleeping with the LED on. USB stays off while asleep: see field_mode().
static void sleep_until_clock(uint32_t t) {
  console_usb_stop();
  for (;;) {
    uint32_t ms, now = hw_clock_read(&ms);
    if (now >= t) break;
    uint32_t left = (t - now) * 1000u - ms;
    hw_watchdog_kick();
    if (left > 10000) left = 10000;
    if (left > 400) {
      pin_write(LED_USER, 1); hw_stop_ms(30);
      pin_write(LED_USER, 0); hw_stop_ms(170);
      pin_write(LED_USER, 1); hw_stop_ms(30);
      pin_write(LED_USER, 0); left -= 230;
    }
    hw_stop_ms(left);
  }
}

// A sample every cfg.sample_s (on multiples of it in device time, so a reset doesn't shift the schedule), an upload
// once cfg.batch samples are waiting, and one straight away at start-up so a deployment shows on the server at once
// (not after a watchdog reset: a fault that keeps resetting mustn't drain the cell through the modem).
// USB: on battery it's off except during uploads. A USB host seen during an upload ends field mode (the console
// comes back); or press RESET with USB plugged in. Started from the console with USB present: no Stop mode, and
// any key stops it.
void field_mode(void) {
  bool usb_at_start = tud_mounted();
  bool lse = hw_clock_init();
  cprintf("field mode: a sample every %lu s, an upload once %lu are waiting, to %s. Clock on the %s%s, %lu record(s) "
          "waiting.\n%s", (unsigned long)cfg.sample_s, (unsigned long)cfg.batch, cfg.url, lse ? "LSE" : "LSI",
          hw_clock_fresh() ? " (restarted)" : "", store_unsent(),
          usb_at_start ? "USB is present, so no Stop mode. Any key stops it.\n"
                       : "Stop mode in between. USB comes on only for uploads: plug it in and press RESET for the console.\n");
  hw_watchdog_start();                                          // a hang now ends in a reset, then field mode again
  field_active = true;
  if (locked_out()) {                                           // parked before this reset
    int mv = cell_mv();
    if (mv >= 0 && mv < BATT_RESUME_MV) {
      if (usb_at_start) { cprintf("field: cell %d mV, still parked until %d mV\n", mv, BATT_RESUME_MV); goto stop; }
      park();
    }
    fstate_set(0, false);
    cprintf("field: cell %d mV: no longer parked\n", mv);
  }
  bool upload_now = !(hw_reset_flags() & RCC_CSR_IWDGRSTF);
  uint32_t next_sample = 0;
  for (;;) {
    uint32_t now = hw_clock_s();
    if (now >= next_sample) {
      sample_take();
      next_sample = (now / cfg.sample_s + 1u) * cfg.sample_s;
      int mv = cell_mv();
      if (mv >= 0 && mv < BATT_STOP_MV) upload_now = true;      // the last upload now, not at the next batch
    }
    if (upload_now || upload_due(now)) {
      upload_now = false;
      if (!usb_at_start) console_usb_start();
      field_upload();
      if (!usb_at_start && tud_mounted()) break;                // a USB host appeared during the upload
      if (locked_out()) {
        if (usb_at_start) { cputs("field: cell flat, field mode stopped\n"); break; }
        park();
      }
    }
    uint32_t wake = next_sample, r = retry_at();
    if (store_unsent() >= cfg.batch && r > now && r < wake) wake = r;
    if (!usb_at_start) { sleep_until_clock(wake); continue; }
    while (hw_clock_s() < wake) { system_poll(); if (console_getc() >= 0) goto stop; }
  }
stop:
  field_active = false;
  cputs("field mode stopped (the watchdog keeps running until the next reset)\n");
}
