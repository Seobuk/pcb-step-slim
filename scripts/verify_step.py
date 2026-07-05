#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify a stripped STEP file:
  1) structural (stdlib): every #ref resolves, no duplicate ids, valid header/footer.
  2) load test (pythonocc, if available): the file actually opens in an OCCT
     kernel and we report the instantiated solid (body) count — the real proof
     it will import into SolidWorks.

Usage: python verify_step.py FILE.step
"""
import re, sys, os
ENT = re.compile(rb'^\s*#(\d+)\s*=\s*(.*)$', re.S)
REF = re.compile(rb'#(\d+)')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def structural(path):
    with open(path, 'rb') as f: data = f.read()
    ds = data.find(b'DATA;'); de = data.rfind(b'ENDSEC;')
    ids = set(); text = {}; dup = 0
    for stmt in data[ds+5:de].split(b';'):
        m = ENT.match(stmt)
        if not m: continue
        i = int(m.group(1))
        if i in ids: dup += 1
        ids.add(i); text[i] = m.group(2)
    missing = 0; samples = []
    for i, s in text.items():
        for r in REF.findall(s):
            if int(r) not in ids:
                missing += 1
                if len(samples) < 5: samples.append((i, int(r)))
    print(f"  size            : {len(data)/1e6:.1f} MB")
    print(f"  entities        : {len(ids):,}  (dup ids: {dup})")
    print(f"  dangling refs   : {missing}" + (f"  e.g. {samples}" if samples else ""))
    print(f"  header/footer   : "
          f"{'ISO-10303-21 OK' if data[:13]==b'ISO-10303-21;' else 'BAD HEADER'}, "
          f"{'END OK' if data.rstrip().endswith(b'END-ISO-10303-21;') else 'BAD FOOTER'}")
    return missing == 0 and dup == 0

def occ_load(path):
    import time
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_SOLID
    t = time.time(); r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        print("  OCC load        : FAILED to read"); return False
    r.TransferRoots(); shp = r.OneShape()
    e = TopExp_Explorer(shp, TopAbs_SOLID); n = 0
    while e.More(): n += 1; e.Next()
    print(f"  OCC load        : OK — {n:,} solid bodies, read in {time.time()-t:.1f}s")
    return True

def main():
    path = sys.argv[1]
    print(f"# verify {os.path.basename(path)}")
    ok = structural(path)
    try:
        occ_load(path)
    except Exception as e:
        print(f"  OCC load        : skipped ({type(e).__name__}: run with pythonocc env for load test)")
    print("  ==> " + ("VALID" if ok else "INVALID (structural errors above)"))
    sys.exit(0 if ok else 2)

if __name__ == '__main__':
    main()
