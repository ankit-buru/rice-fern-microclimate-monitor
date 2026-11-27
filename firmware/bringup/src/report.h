// Uploads to the server (HTTP POST of status + stored samples; settings and acks come back in the reply), sampling,
// and field mode: a sample every cfg.sample_s, an upload every cfg.batch samples.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

bool dns_check(const char *host);                                                 // print the DNS servers, resolve host
int  http_post(const char *path, const char *body, char *reply, size_t replylen);   // HTTP status, or -1

#define BATT_LOW_MV    3400                // flagged "low" below this (rest voltage)
#define BATT_STOP_MV   3300                // one last upload, then none (DESIGN.md §4.7; the DW01A cuts off at ~2.5 V)
#define BATT_RESUME_MV 3500                // a reset un-parks the board only above this

uint32_t sample_take(void);                // read and store one sample now; returns its number (0 = failed)
bool upload_session(bool power_off_after, int batt);   // modem on, send everything waiting; batt 0 ok 1 low 2 last 3 locked
bool report_now(bool power_off_after);     // console "report": upload_session with the battery state, no lockout
extern bool field_active;                  // LED pattern while field mode runs
void field_mode(void);                     // sample/upload forever (until USB appears, or a key with USB at the start)
