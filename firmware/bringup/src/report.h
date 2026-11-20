// Reporting to the test server: one JSON status report per check-in, commands come back in the HTTP reply.
#pragma once
#include <stdbool.h>
#include <stddef.h>

bool dns_check(const char *host);                                                 // print the DNS servers, resolve host
int  http_post(const char *path, const char *body, char *reply, size_t replylen);   // HTTP status, or -1
bool report_cycle(bool power_off_after);   // modem on, register, data, POST, apply the reply, (modem off)
extern bool field_active;                 // LED pattern while field mode runs
#define FIELD_MIN_MV 3300                  // no uploads below this cell voltage (DESIGN.md §4.7)
void field_mode(void);                     // report every cfg.interval_s until a key is pressed or USB appears
