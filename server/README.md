# Test server

A small server for the boards to report to while AWS isn't set up: [test_server.py](test_server.py), one file,
Python 3.8+ standard library only (nothing to install).

## Run

```bash
python3 test_server.py serve --port 7070 --token <a-secret>
```

The boards connect out over LTE, so the port must be reachable from the internet: forward TCP 7070 on your router
to this machine and allow it through the machine's firewall. `curl ifconfig.me` shows the public address.

Reports are stored under `data/` (git-ignored): `data/<board id>.jsonl`, one JSON object per report, plus the
server's receive time and the source IP.

- `http://localhost:7070/`: every board and its latest report (refreshes every minute)
- `http://localhost:7070/device/<id>`: one board's last 200 uploads (status); add `.csv` to download all of them
- `http://localhost:7070/device/<id>/samples`: its last 200 samples (logger firmware); `/samples.csv` for all of them

Logger firmware sends its stored samples with each upload, up to 24 per POST; the reply's `ack` tells the board which
it can forget. Duplicates (a resend after a dropped connection) are dropped by epoch + sequence number. A board's
clock only counts seconds since its cell was connected, so the server converts: real time = receive time - (board
clock in the POST - board clock in the sample). Samples land in `data/<board id>.samples.jsonl`.
A power cut (cell swap) restarts the board's clock and starts a new clock run (`run` in each POST and, from record
layout 3, in each sample); `log` on the console shows it, and `log clear` starts a new epoch at run 1. The server
times each sample from the latest upload in its own (epoch, run), so samples left unsent at a cell swap keep their
real times; a run that never got an upload through leaves its samples with an empty `time` and `time-unknown`.

Starting a board over completely: on its console, `factory yes` erases its settings (server, token, name, schedule),
every stored sample and its clock, picks a random new epoch and reboots; set `cfg url`, `cfg token` and `cfg name`
again. On the server, `python3 test_server.py archive <board-id>` moves that board's files to
`data/archive/<id>-<time>/` (works while the server runs), so its pages start empty. `cfg name <label>` sets a label
that shows in the `name` column; the board's key on the server is always its MCU unique ID.

Logger-2 records carry the Qwiic sensors as raw counts; the server adds real units: `temp_c` / `rh_pct` (AHT20),
`lux` (VEML7700), `uva_uw_cm2` / `uvb_uw_cm2` / `uvc_uw_cm2` (AS7331). Light and UV are measured twice per sample,
at a sensitive "shade" setting and a wide-range "sun" setting; `lux_from` / `uv_from` say which one was used (the
shade one unless it saturated). The raw counts for both are kept in the CSV (`als_shade`, `uva_sun`, ...).

## Send a board a command

Commands wait on the server and go out in the reply to the board's next report (the board only connects out, and
powers its modem off between reports):

```bash
python3 test_server.py queue <board id> sample_s=900 batch=4
```

Logger firmware acts on `sample_s` (seconds between samples, 60 minimum) and `batch` (upload once this many samples
are waiting, 1-96), both saved to its EEPROM. Older bring-up firmware acted on `interval_s` instead.

## Point a board at it

In the board's console:

```
cfg url http://<public ip>:7070
cfg token <a-secret>
report
```

`report` uploads everything waiting and powers the modem off afterwards. `sample` stores one sample, `log` lists
them, `cfg sample <s>` / `cfg batch <n>` set the schedule. `field` runs the schedule (a sample every `sample_s`, an
upload once `batch` are waiting, and one upload straight away). A board that boots with no USB host (on its battery)
starts field mode by itself after about 15 s.

## Plot a board's battery

```bash
curl -s -o board.csv http://<server>:7070/device/<board id>.csv
python3 plot_battery.py board.csv battery.png      # needs: pip install matplotlib numpy
```

State of charge with a projection to empty, plus the cell voltage at rest (before the modem powers on) and under
load (just registered). Reports from `bringup-2` firmware onwards carry the extra power fields: `pre_mv`, `reg_mv`,
`prev_post_mv`, `prev_off_mv` (the `prev_` ones were measured after the previous report had gone), `crate_raw`
(0.208 %/h per step), `hibrt`, `on_ms`, `meas_ms`, `prev_cycle_ms`, and the modem's serving-cell readout `ceng`
with transmit power `reg_tx` / `prev_post_tx` (0.1 dBm; 255 means not transmitting).
