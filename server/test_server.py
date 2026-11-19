#!/usr/bin/env python3
"""TreeWeather test server: receives the boards' JSON reports and hands back queued commands.

Python 3.8+ standard library only. Data lives in plain files under --data (default ./data):
  <id>.jsonl          one JSON object per report, as received plus the server's "rx_time" and "rx_ip"
  <id>.pending.json   commands waiting for the board's next check-in (written by "queue", cleared on delivery)

  python3 test_server.py serve [--port 7070] [--token SECRET] [--data DIR]
  python3 test_server.py queue <board-id> interval_s=600 [key=value ...]
  python3 test_server.py show [<board-id>]

HTTP:
  POST /report        board -> server. Header X-Token must match --token if one is set.
                      Reply: {"ok": true, "server_time": <unix s>, ...queued commands...}
  GET  /              overview page: every board and its latest report
  GET  /device/<id>   the last 200 reports as a table;  /device/<id>.csv  all of them as CSV
"""
import argparse
import csv
import html
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 8192
ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,48}$")
# columns shown first on the pages (anything else the board sends follows)
COLUMNS = ["rx_time", "seq", "uptime_s", "usb", "vcell_mv", "soc_pct_x100", "vdda_mv", "csq", "rsrp", "rsrq",
           "sinr", "band", "plmn", "reg_ms", "interval_s", "reset", "rx_ip"]


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, root):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def path(self, dev, suffix):
        if not ID_RE.match(dev):
            raise ValueError("bad board id")
        return os.path.join(self.root, dev + suffix)

    def append(self, dev, rec):
        with open(self.path(dev, ".jsonl"), "a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def history(self, dev, last=None):
        try:
            with open(self.path(dev, ".jsonl")) as f:
                rows = [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []
        return rows[-last:] if last else rows

    def devices(self):
        return sorted(n[:-6] for n in os.listdir(self.root) if n.endswith(".jsonl"))

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


def table(rows, link_ids=False):
    keys = ["id"] + list(COLUMNS) if link_ids else list(COLUMNS)
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
                rec = json.loads(self.rfile.read(n))
                dev = str(rec["id"])
                rec["rx_time"] = now_iso()
                rec["rx_ip"] = self.client_address[0]
                store.append(dev, rec)
                reply = {"ok": True, "server_time": int(time.time())}
                cmds = store.take_pending(dev)
                reply.update(cmds)
            except (ValueError, KeyError) as e:
                return self.send(400, json.dumps({"ok": False, "error": str(e)}))
            self.log_message("report from %s seq %s%s", dev, rec.get("seq"), f", delivered {cmds}" if cmds else "")
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
            m = re.match(r"^/device/([0-9A-Za-z_-]+)(\.csv)?$", path)
            if m:
                dev, as_csv = m.group(1), m.group(2)
                rows = store.history(dev, None if as_csv else 200)
                if as_csv:
                    keys = list(dict.fromkeys(k for r in rows for k in r))
                    buf = io.StringIO()
                    w = csv.DictWriter(buf, fieldnames=keys)
                    w.writeheader()
                    w.writerows(rows)
                    return self.send(200, buf.getvalue(), "text/csv")
                body = f'<p><a href="/">all boards</a> | <a href="/device/{dev}.csv">CSV</a></p>' + (table(rows) if rows else "no reports")
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
