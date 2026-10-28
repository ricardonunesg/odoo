"""Compara duas fotografias (snapshot.py) e mostra as diferenças por secção."""
import sys
from collections import defaultdict


def load(p):
    d = {}
    for line in open(p):
        sec, key, val = line.rstrip("\n").split("|", 2)
        d[(sec, key)] = val
    return d


a, b = load(sys.argv[1]), load(sys.argv[2])
out = defaultdict(list)
for k in sorted(set(a) | set(b)):
    va, vb = a.get(k), b.get(k)
    if va != vb:
        if va is None:
            out[k[0]].append(f"  + {k[1]}: {vb}")
        elif vb is None:
            out[k[0]].append(f"  - {k[1]}: {va}")
        else:
            out[k[0]].append(f"  ~ {k[1]}: {va}  →  {vb}")
if not out:
    print("SEM DIFERENÇAS")
for sec, lst in out.items():
    print(f"[{sec}] {len(lst)} diferença(s)")
    for x in lst[:int(sys.argv[3]) if len(sys.argv) > 3 else 15]:
        print(x[:330])
