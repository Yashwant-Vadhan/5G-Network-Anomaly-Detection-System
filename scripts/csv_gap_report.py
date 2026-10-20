#!/usr/bin/env python3
"""Summarise a collector CSV (C1 format): header check, rows, duration, sampling interval, gaps, NA counts.
Usage: python scripts/csv_gap_report.py file.csv [--gap 5]   (timestamps are dd-MM-yy HH:mm:ss, device-local)"""
import sys, csv, statistics as st
from datetime import datetime
HEADER = "timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn".split(",")
if len(sys.argv) < 2: sys.exit(__doc__)
path = sys.argv[1]; gap = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 5.0
rows = list(csv.reader(open(path, encoding="utf-8")))
hdr, data = rows[0], [r for r in rows[1:] if r]
print(f"file: {path}\nheader matches C1 (18 columns): {hdr == HEADER}" + ("" if hdr == HEADER else f"  GOT: {hdr}"))
ts = []
for r in data:
    try: ts.append(datetime.strptime(r[0].strip(), "%d-%m-%y %H:%M:%S"))
    except Exception: print("  unparseable timestamp:", r[0])
print(f"rows: {len(data)}")
if len(ts) > 1:
    d = [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
    print(f"start: {ts[0]}  end: {ts[-1]}  duration: {(ts[-1]-ts[0]).total_seconds()/60:.1f} min")
    print(f"interval median {st.median(d):.1f}s, mean {st.mean(d):.2f}s, max {max(d):.0f}s; expected rows at 3 s: {int((ts[-1]-ts[0]).total_seconds()/3)+1}")
    big = [(ts[i], d[i]) for i in range(len(d)) if d[i] > gap]
    print(f"gaps > {gap:.0f}s: {len(big)}" + ("" if not big else " -> " + "; ".join(f"{t:%H:%M:%S} (+{s:.0f}s)" for t, s in big[:15])))
    dup = sum(1 for x in d if x == 0); print(f"duplicate timestamps: {dup}")
na = {h: sum(1 for r in data if len(r) > i and r[i].strip() in ("NA", "")) for i, h in enumerate(hdr)}
print("NA/empty per column (non-zero only):", {k: v for k, v in na.items() if v})
