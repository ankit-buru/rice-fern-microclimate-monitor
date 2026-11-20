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
- `http://localhost:7070/device/<id>`: one board's last 200 reports; add `.csv` to download all of them

## Send a board a command

Commands wait on the server and go out in the reply to the board's next report (the board only connects out, and
powers its modem off between reports):

```bash
python3 test_server.py queue <board id> interval_s=600
```

The bring-up firmware acts on `interval_s` (60 s minimum, saved to its EEPROM) and prints anything else it receives.

## Point a board at it

In the board's console:

```
cfg url http://<public ip>:7070
cfg token <a-secret>
report
```

`report` does one check-in and powers the modem off afterwards. `field` reports every interval until a key is
pressed. A board that boots with no USB host (on its battery) starts field mode by itself after about 15 s.

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
