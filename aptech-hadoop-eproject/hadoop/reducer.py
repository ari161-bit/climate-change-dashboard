#!/usr/bin/env python
"""MapReduce reducer: sums counts per year -> "year<TAB>total"."""
import sys
cur, total = None, 0
for line in sys.stdin:
    key, val = line.rstrip("\n").split("\t")
    if key != cur:
        if cur is not None:
            print(f"{cur}\t{total}")
        cur, total = key, 0
    total += int(val)
if cur is not None:
    print(f"{cur}\t{total}")
