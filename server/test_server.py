#!/usr/bin/env python3
"""TreeWeather test server: receives the boards' JSON reports and hands back queued commands.

Python 3.8+ standard library only. Data lives in plain files under --data (default ./data):
  <id>.jsonl          one JSON object per POST (the board's status), as received minus "recs", plus the server's
                      "rx_time", "rx_ip" and "n_recs"
  <id>.samples.jsonl  one JSON object per stored sample (logger firmware), duplicates dropped, with its real time
  <id>.pending.json   commands waiting for the board's next check-in (written by "queue", cleared on delivery)

  python3 test_server.py serve [--port 7070] [--token SECRET] [--data DIR]
  python3 test_server.py queue <board-id> interval_s=600 [key=value ...]
  python3 test_server.py show [<board-id>]
  python3 test_server.py archive <board-id>   move the board's files to data/archive/<id>-<time>/ (the server, even
                      while running, then treats it as a new board; pair with "factory yes" on the board)

HTTP:
  POST /report        board -> server. Header X-Token must match --token if one is set.
                      Body: a status object; logger firmware adds "recs": [[seq, t, mv, mcu_c, s0, s1, s2, flags], ...],
                      "ep" (store epoch), "now" + "now_ms" (the board's clock when it built the POST).
                      Reply: {"ok": true, "server_time": <unix s>, "ack": <last seq saved>, ...queued commands...}
  GET  /              overview page: every board and its latest report
  GET  /device/<id>   the last 200 reports as a table;  /device/<id>.csv  all of them as CSV
  GET  /device/<id>/samples   the last 200 samples;   /device/<id>/samples.csv  all of them as CSV

Sample times: a board's clock counts seconds from when its cell was connected, never set to real time. The server
converts: real time = receive time - (board clock in the POST - board clock in the sample). The error is the upload
latency (seconds) plus the board's crystal drift (~2 s/day of backlog). A power cut restarts the clock from 0 and
starts a new clock run ("run", firmware rv 3); each record carries the run it was taken in, and is timed with the
offset (receive time - board clock) of the latest upload made in that same (epoch, run), so records left unsent at a
cell swap keep their real times. A record from a run that never got an upload through has no time ("time" empty,
flag "time-unknown"). Records without a run (rv 2) are timed with the current upload, as before.
"""
import argparse
import csv
import html
import io
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 8192
ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,48}$")
# columns shown first on the pages (anything else the board sends follows)
COLUMNS = ["name", "rx_time", "fw", "git", "n_recs", "first", "last", "newest", "acked", "post", "batt", "backoff", "vcell_mv",
           "soc_pct_x100", "csq", "rsrp", "sinr", "band", "plmn", "reg_ms", "sample_s", "batch", "reset", "uptime_s",
           "seq", "interval_s", "rx_ip"]
SAMPLE_COLUMNS = ["seq", "time", "vcell_mv", "mcu_c", "temp_c", "rh_pct", "lux", "uva_uw_cm2", "uvb_uw_cm2",
                  "uvc_uw_cm2", "flag_names", "sensors", "t_dev", "ep", "run", "unix", "rx_time"]
SAMPLE_FLAGS = {1: "boot", 2: "clock-new", 4: "batt-low", 8: "locked-out", 16: "usb"}
SENSOR_BITS = {1: "aht20", 2: "veml7700", 4: "as7331", 8: "uv-shade-ovf", 16: "uv-sun-ovf", 32: "aht-crc"}

# Record layout 2 (fw logger-2, "rv": 2): [seq, t, mv, mcu_c, flags, sensors, aht_t (0.01 C), aht_rh (0.01 %),
#   als_shade, white_shade, als_sun, white_sun, uva_shade, uvb_shade, uvc_shade, uva_sun, uvb_sun, uvc_sun, as_temp]
# Layout 3 ("rv": 3) adds a 20th field: the clock run (low 8 bits of the POST's "run") the sample was taken in.
# VEML7700 lux/count = 0.0036 * (800 / IT_ms) * (2 / gain) (Adafruit_VEML7700): shade gain 2, 100 ms; sun 1/8, 25 ms.
# AS7331 uW/cm2 = counts * FSR / (gain * ms * 1024) (SparkFun_AS7331), FSR A/B/C 348160/387072/169984:
#   shade gain 256, 64 ms; sun gain 16, 64 ms. Chip temperature C = raw * 0.05 - 66.9.
VEML_LUX = (0.0036 * 8 * 1, 0.0036 * 32 * 16)
UV_FSR = (348160, 387072, 169984)
UV_SCALE = (1 / (256 * 64 * 1024), 1 / (16 * 64 * 1024))
SAT = 60000                                      # counts: treat as saturated (16-bit full scale 65535)


def names(bits, table):
    return " ".join(n for b, n in table.items() if bits & b)


def decode_record(r):
    """One record array from a board -> a row of real units (raw counts kept too). Layout 1 (logger-1) has 8 fields."""
    row = {"seq": int(r[0]), "vcell_mv": r[2], "mcu_c": r[3]}
    if len(r) == 8:                              # logger-1: [seq, t, mv, mcu_c, s0, s1, s2, flags]
        row.update({"flags": int(r[7]), "flag_names": names(int(r[7]), SAMPLE_FLAGS)})
        return row
    (_, _, _, _, flags, sens, aht_t, aht_rh, als0, wh0, als1, wh1, a0, b0, c0, a1, b1, c1, as_t) = r[:19]
    row.update({"flags": flags, "flag_names": names(flags, SAMPLE_FLAGS), "sensors": names(sens, SENSOR_BITS)})
    if sens & 1:
        row.update({"temp_c": aht_t / 100, "rh_pct": aht_rh / 100})
    if sens & 2:
        shade_ok = als0 < SAT
        row["lux"] = round(als0 * VEML_LUX[0], 3) if shade_ok else round(als1 * VEML_LUX[1], 1)
        row["lux_from"] = "shade" if shade_ok else "sun"
        row.update({"als_shade": als0, "white_shade": wh0, "als_sun": als1, "white_sun": wh1})
    if sens & 4:
        shade = (a0, b0, c0)
        use_shade = not (sens & 8) and max(shade) < SAT
        counts, scale = (shade, UV_SCALE[0]) if use_shade else ((a1, b1, c1), UV_SCALE[1])
        for name, n, fsr in zip(("uva", "uvb", "uvc"), counts, UV_FSR):
            row[f"{name}_uw_cm2"] = round(n * fsr * scale, 4)
        row["uv_from"] = "shade" if use_shade else "sun"
        row.update({"uva_shade": a0, "uvb_shade": b0, "uvc_shade": c0, "uva_sun": a1, "uvb_sun": b1, "uvc_sun": c1,
                    "as7331_c": round(as_t * 0.05 - 66.9, 2)})
    return row


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.seen = {}                      # board id -> {(epoch, seq)} already stored
        self.clk = {}                       # board id -> {(epoch, run & 0xFF): real time - board clock}, latest upload
        os.makedirs(root, exist_ok=True)

    def path(self, dev, suffix):
        if not ID_RE.match(dev):
            raise ValueError("bad board id")
        return os.path.join(self.root, dev + suffix)

    def append(self, dev, rec):
        with open(self.path(dev, ".jsonl"), "a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def history(self, dev, last=None, suffix=".jsonl"):
        try:
            with open(self.path(dev, suffix)) as f:
                rows = [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []
        return rows[-last:] if last else rows

    def clock_offsets(self, dev):
        """(epoch, run & 0xFF) -> offset from the latest upload in that clock run (rebuilt from <id>.jsonl)."""
        clk = self.clk.get(dev)
        if clk is None or not os.path.exists(self.path(dev, ".jsonl")):   # (no file: never seen, or archived)
            clk = {(r.get("ep"), r["run"] & 0xFF): r["clk_off"] for r in self.history(dev)
                   if "clk_off" in r and r.get("run") is not None}
            self.clk[dev] = clk
        return clk

    def note_clock(self, dev, ep, run, offset):
        with self.lock:
            self.clock_offsets(dev)[(ep, run & 0xFF)] = offset

    def add_samples(self, dev, ep, dev_now, rx_unix, rx_iso, recs):
        """Append the new ones (by epoch + seq); returns the highest seq in the batch, or None if it was empty."""
        with self.lock:
            seen = self.seen.get(dev)
            if seen is None or not os.path.exists(self.path(dev, ".samples.jsonl")):   # archived: start afresh
                seen = {(r.get("ep"), r.get("seq")) for r in self.history(dev, suffix=".samples.jsonl")}
                self.seen[dev] = seen
            clk = self.clock_offsets(dev)
            top = None
            with open(self.path(dev, ".samples.jsonl"), "a") as f:
                for r in recs:
                    seq, t = int(r[0]), int(r[1])
                    top = seq if top is None else max(top, seq)
                    if (ep, seq) in seen:
                        continue
                    seen.add((ep, seq))
                    row = decode_record(r)
                    if len(r) >= 20:                     # rv 3: time it from an upload in its own clock run
                        run = int(r[19])
                        off = clk.get((ep, run))
                        unix = None if off is None else off + t
                        row["run"] = run
                    else:
                        unix = rx_unix - (dev_now - t)
                    if unix is None:
                        row["flag_names"] = (row.get("flag_names", "") + " time-unknown").strip()
                    row.update({"time": "" if unix is None else
                                datetime.fromtimestamp(round(unix), timezone.utc).astimezone().isoformat(timespec="seconds"),
                                "t_dev": t, "ep": ep, "unix": None if unix is None else round(unix, 1), "rx_time": rx_iso})
                    f.write(json.dumps(row, separators=(",", ":")) + "\n")
            return top

    def devices(self):
        return sorted(n[:-6] for n in os.listdir(self.root) if n.endswith(".jsonl") and not n.endswith(".samples.jsonl"))

    def archive(self, dev):
        """Move every file of this board into archive/<id>-<local time>/; returns that folder, or None if none."""
        files = [self.path(dev, s) for s in (".jsonl", ".samples.jsonl", ".pending.json")]
        files = [f for f in files if os.path.exists(f)]
        if not files:
            return None
        dest = os.path.join(self.root, "archive", dev + "-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        os.makedirs(dest)
        for f in files:
            os.rename(f, os.path.join(dest, os.path.basename(f)))
        return dest

    def take_pending(self, dev):
        p = self.path(dev, ".pending.json")
        try:
            with open(p) as f:
                cmds = json.load(f)
        except FileNotFoundError:
            return {}
        os.remove(p)
        return cmds

    def queue(self, dev, cmds):
        p = self.path(dev, ".pending.json")
        cur = {}
        if os.path.exists(p):
            with open(p) as f:
                cur = json.load(f)
        cur.update(cmds)
        with open(p, "w") as f:
            json.dump(cur, f, indent=1)
        return cur


def table(rows, link_ids=False, columns=COLUMNS):
    keys = ["id"] + list(columns) if link_ids else list(columns)
    for r in rows:
        keys += [k for k in r if k not in keys and k != "id"]
    keys = [k for k in keys if any(k in r for r in rows)]
    out = ["<table><tr>" + "".join(f"<th>{html.escape(k)}</th>" for k in keys) + "</tr>"]
    for r in reversed(rows):
        cells = []
        for k in keys:
            v = html.escape(str(r.get(k, "")))
            cells.append(f'<td><a href="/device/{v}">{v}</a></td>' if link_ids and k == "id" else f"<td>{v}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(out) + "</table>"


def to_csv(rows, first=()):
    keys = list(dict.fromkeys(list(first) + [k for r in rows for k in r]))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><title>{title}</title>
<style>body{{font:14px system-ui,sans-serif;margin:16px}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:2px 6px;text-align:right;white-space:nowrap}}th{{background:#eee}}</style>
<h2>{title}</h2>{body}"""


def make_handler(store, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "treeweather-test/1"

        def send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path.split("?")[0] != "/report":
                return self.send(404, '{"ok":false,"error":"not found"}')
            if token and self.headers.get("X-Token") != token:
                return self.send(401, '{"ok":false,"error":"bad token"}')
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self.send(400, '{"ok":false,"error":"bad length"}')
            try:
                rx_unix = time.time()
                rec = json.loads(self.rfile.read(n))
                dev = str(rec["id"])
                recs = rec.pop("recs", None)
                rec["rx_time"] = now_iso()
                rec["rx_ip"] = self.client_address[0]
                reply = {"ok": True, "server_time": int(rx_unix)}
                timed = "now" in rec and rec.get("run") is not None   # rv 3: this upload times its clock run
                if timed:
                    rec["clk_off"] = round(rx_unix - (float(rec["now"]) + float(rec.get("now_ms", 0)) / 1000), 1)
                if recs is not None:
                    rec["n_recs"] = len(recs)
                    if recs:
                        rec["first"], rec["last"] = recs[0][0], recs[-1][0]
                store.append(dev, rec)                   # first: the caches treat a missing <id>.jsonl as "archived"
                if timed:
                    store.note_clock(dev, rec.get("ep", 0), int(rec["run"]), rec["clk_off"])
                if recs:
                    dev_now = float(rec["now"]) + float(rec.get("now_ms", 0)) / 1000
                    reply["ack"] = store.add_samples(dev, rec.get("ep", 0), dev_now, rx_unix, rec["rx_time"], recs)
                cmds = store.take_pending(dev)
                reply.update(cmds)
            except (ValueError, KeyError) as e:
                return self.send(400, json.dumps({"ok": False, "error": str(e)}))
            what = f"records {rec['first']}-{rec['last']}" if rec.get("n_recs") else f"seq {rec.get('seq')}"
            self.log_message("report from %s, %s%s", dev, what, f", delivered {cmds}" if cmds else "")
            self.send(200, json.dumps(reply, separators=(",", ":")))

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                rows = []
                for dev in store.devices():
                    h = store.history(dev, 1)
                    if h:
                        rows.append({**h[-1], "id": dev})
                body = ("<p>Latest report from each board (click an id for its history):</p>" + table(rows, link_ids=True)) if rows else "no reports yet"
                return self.send(200, PAGE.format(title="TreeWeather boards", body=body), "text/html; charset=utf-8")
            m = re.match(r"^/device/([0-9A-Za-z_-]+)/samples(\.csv)?$", path)
            if m:
                dev, as_csv = m.group(1), m.group(2)
                rows = store.history(dev, None if as_csv else 200, suffix=".samples.jsonl")
                if as_csv:
                    return self.send(200, to_csv(rows, SAMPLE_COLUMNS), "text/csv")
                body = (f'<p><a href="/">all boards</a> | <a href="/device/{dev}">uploads</a> | '
                        f'<a href="/device/{dev}/samples.csv">CSV</a></p>' + (table(rows, columns=SAMPLE_COLUMNS) if rows else "no samples"))
                return self.send(200, PAGE.format(title=f"Board {html.escape(dev)}: samples", body=body), "text/html; charset=utf-8")
            m = re.match(r"^/device/([0-9A-Za-z_-]+)(\.csv)?$", path)
            if m:
                dev, as_csv = m.group(1), m.group(2)
                rows = store.history(dev, None if as_csv else 200)
                if as_csv:
                    return self.send(200, to_csv(rows), "text/csv")
                body = (f'<p><a href="/">all boards</a> | <a href="/device/{dev}.csv">CSV</a> | '
                        f'<a href="/device/{dev}/samples">samples</a></p>' + (table(rows) if rows else "no reports"))
                return self.send(200, PAGE.format(title=f"Board {html.escape(dev)}", body=body), "text/html; charset=utf-8")
            self.send(404, "not found", "text/plain")

    return Handler


def parse_value(v):
    try:
        return json.loads(v)
    except ValueError:
        return v


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=7070)
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--token", default=os.environ.get("TW_TOKEN", ""))
    q = sub.add_parser("queue")
    q.add_argument("id")
    q.add_argument("assignments", nargs="+", help="key=value, e.g. interval_s=600")
    ar = sub.add_parser("archive", help="move a board's data to data/archive/ so it starts afresh")
    ar.add_argument("id")
    sh = sub.add_parser("show")
    sh.add_argument("id", nargs="?")
    a = ap.parse_args()
    store = Store(a.data)

    if a.cmd == "serve":
        if not a.token:
            print("warning: no --token: anyone who finds the port can post reports", file=sys.stderr)
        httpd = ThreadingHTTPServer((a.host, a.port), make_handler(store, a.token))
        print(f"listening on {a.host}:{a.port}, data in {a.data}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    elif a.cmd == "archive":
        dest = store.archive(a.id)
        print(f"archived {a.id} to {dest}" if dest else f"no data for {a.id}")
    elif a.cmd == "queue":
        cmds = {}
        for kv in a.assignments:
            k, _, v = kv.partition("=")
            cmds[k] = parse_value(v)
        print(f"queued for {a.id}: {store.queue(a.id, cmds)}")
    elif a.cmd == "show":
        for dev in [a.id] if a.id else store.devices():
            for r in store.history(dev, 5):
                print(dev, json.dumps(r))


if __name__ == "__main__":
    main()
