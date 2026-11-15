#!/usr/bin/env python
"""MapReduce mapper: Disaster.csv rows -> "year<TAB>count" for TOTAL disaster rows.
Missing / blank values are skipped (handles incomplete data)."""
import sys, csv
reader = csv.reader(sys.stdin)
header = None
for row in reader:
    if header is None:
        header = [h.lstrip("\ufeff") for h in row]
        years = [(i, h) for i, h in enumerate(header) if h.isdigit()]
        ind = header.index("Indicator"); iso = header.index("ISO2")
        continue
    if len(row) < len(header) or not row[iso]:
        continue                      # skip aggregates (World etc.) and broken rows
    if not row[ind].endswith("Number of Disasters: TOTAL"):
        continue
    for i, y in years:
        v = row[i].strip()
        if v:
            try:
                print(f"{y}\t{int(float(v))}")
            except ValueError:
                pass
