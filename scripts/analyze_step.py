#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze a (KiCad/OpenCASCADE) PCB STEP assembly and recommend what to strip
for a lightweight, SolidWorks-friendly mechanical model.

- Text pass (stdlib, fast, any Python): per-product solids/faces/bytes weight,
  detects board layers (copper/pad/via/silkscreen/soldermask/solder-ball) and
  flat chip passives (R_/C_ footprints), and prints a recommended strip set.
- OCC pass (optional, needs pythonocc-core): exact per top-level component
  height/bbox via XCAF. Enable with --occ (slow + RAM-heavy on huge files).

Usage:
    python analyze_step.py INPUT.step [--occ]
"""
import re, sys, os, argparse, array

REF = re.compile(rb'#(\d+)')
QS  = re.compile(rb"'((?:[^']|'')*)'")
ENT = re.compile(rb'^\s*#(\d+)\s*=\s*(.*)$', re.S)

# product-name fragments that are non-mechanical PCB detail (safe to strip)
LAYER_KEYS = ('_copper', '_pad', '_via', '_silkscreen', '_soldermask',
              '_paste', 'SOLDER_BALL')
# flat SMD chip-passive footprints (height < ~1.6mm) — strip
CHIP_FOOTPRINTS = ('C_0201', 'C_0402', 'C_0603', 'C_0805', 'C_1206',
                   'R_0201', 'R_0402', 'R_0603', 'R_0805', 'R_1206')

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def log(*a): print(*a, flush=True)

def parse(path):
    with open(path, 'rb') as f:
        data = f.read()
    ds = data.find(b'DATA;'); de = data.rfind(b'ENDSEC;')
    body = data[ds+5:de]
    text, order, mx = {}, [], 0
    for stmt in body.split(b';'):
        m = ENT.match(stmt)
        if not m: continue
        i = int(m.group(1)); text[i] = m.group(2).strip(); order.append(i)
        if i > mx: mx = i
    return data, text, order, mx

def text_profile(path):
    """Roll up geometry weight by TOP-LEVEL component (direct child of the root
    assembly), grouped by product name. Each distinct part prototype is counted
    once, so copper/pad/via report their true bulk and shared chip prototypes are
    not multiplied by their instance count."""
    data, text, order, mx = parse(path)
    nauo = {}; pd_form = {}; form_prod = {}; pname = {}; pds_t = {}; sdr = {}
    for i, s in text.items():
        if s.startswith(b'NEXT_ASSEMBLY_USAGE_OCCURRENCE'):
            st = QS.findall(s); rf = REF.findall(s)
            if len(st) >= 2 and len(rf) >= 2:
                nauo[i] = (st[1].decode('latin-1'), int(rf[0]), int(rf[1]))
        elif s.startswith(b'PRODUCT_DEFINITION('):
            r = REF.findall(s); pd_form[i] = int(r[0]) if r else None
        elif s.startswith(b'PRODUCT_DEFINITION_FORMATION('):
            r = REF.findall(s); form_prod[i] = int(r[0]) if r else None
        elif s.startswith(b'PRODUCT('):
            m = QS.search(s); pname[i] = m.group(1).decode('latin-1') if m else '?'
        elif s.startswith(b'PRODUCT_DEFINITION_SHAPE('):
            r = REF.findall(s); pds_t[i] = int(r[-1]) if r else None
    def prodname(pd):
        f = pd_form.get(pd); p = form_prod.get(f) if f is not None else None
        return pname.get(p, '?') if p is not None else '?'
    for i, s in text.items():
        if s.startswith(b'SHAPE_DEFINITION_REPRESENTATION'):
            r = REF.findall(s)
            if len(r) >= 2 and pds_t.get(int(r[0])) in pd_form:
                sdr[pds_t[int(r[0])]] = int(r[1])

    children = {}                       # parent_pd -> [child_pd]
    for i, (rd, pp, cp) in nauo.items():
        children.setdefault(pp, []).append(cp)

    def local(srid):                    # geometry of one prototype, counted once
        seen = {srid}; stk = [srid]; nf = nb = 0
        while stk:
            x = stk.pop(); t = text.get(x, b''); nb += len(t)
            if t.startswith(b'ADVANCED_FACE'): nf += 1
            for r in REF.findall(t):
                r = int(r)
                if r not in seen and r in text: seen.add(r); stk.append(r)
        return nf, nb
    loc = {pd: local(s) for pd, s in sdr.items()}

    memo = {}
    def subtree(pd):                    # this part + all descendants, each PD once
        if pd in memo: return memo[pd]
        memo[pd] = (0, 0)
        nf, nb = loc.get(pd, (0, 0))
        for c in set(children.get(pd, [])):
            a, b = subtree(c); nf += a; nb += b
        memo[pd] = (nf, nb); return memo[pd]

    parents = set(children); allc = set()
    for v in children.values(): allc.update(v)
    roots = [p for p in parents if p not in allc]

    top_inst = {}                       # distinct top-level child PD -> #placements
    for rt in roots:
        for cp in children.get(rt, []):
            top_inst[cp] = top_inst.get(cp, 0) + 1
    agg = {}                            # product name -> [instances, faces, bytes]
    for cp, ins in top_inst.items():    # bytes counted ONCE per distinct prototype
        nf, nb = subtree(cp); nm = prodname(cp)
        a = agg.setdefault(nm, [0, 0, 0]); a[0] += ins; a[1] += nf; a[2] += nb

    refdes_prod = {}
    cap = re.compile(r'^C\d+$'); res = re.compile(r'^R\d+$')
    for i, (rd, pp, cp) in nauo.items():
        if cap.match(rd) or res.match(rd):
            refdes_prod.setdefault(prodname(cp), set()).add(rd)
    all_names = set(pname.values())     # every product name, at any nesting level
    return agg, refdes_prod, all_names

def classify(agg, refdes_prod):
    layers, chips, tallcaps, comps = [], [], [], []
    for nm, (ins, nf, nb) in agg.items():
        if any(k in nm for k in LAYER_KEYS):
            layers.append((nb, nm, ins, nf))
        elif any(nm.startswith(c) for c in CHIP_FOOTPRINTS):
            chips.append((nb, nm, ins, nf))
        elif nm in refdes_prod and not any(nm.startswith(c) for c in CHIP_FOOTPRINTS):
            tallcaps.append((nb, nm, ins, nf))   # cap/res with a part-number model => keep
        else:
            comps.append((nb, nm, ins, nf))
    return layers, chips, tallcaps, comps

def occ_heights(path):
    """exact per top-level component height via XCAF (pythonocc)."""
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    doc = TDocStd_Document("doc")                       # plain string; do NOT call XCAFApp
    st = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    rd = STEPCAFControl_Reader(); rd.SetNameMode(True)
    if rd.ReadFile(path) != IFSelect_RetDone: return []
    rd.Transfer(doc)
    tops = TDF_LabelSequence(); st.GetFreeShapes(tops)
    rows = []
    for ti in range(1, tops.Length()+1):
        comps = TDF_LabelSequence(); st.GetComponents(tops.Value(ti), comps)
        for i in range(1, comps.Length()+1):
            lab = comps.Value(i); shp = st.GetShape(lab)
            b = Bnd_Box()
            try: brepbndlib.Add(shp, b)
            except Exception: continue
            if b.IsVoid(): continue
            x0, y0, z0, x1, y1, z1 = b.Get()
            rows.append((round(z1-z0, 2), lab.GetLabelName(), round(x1-x0, 2), round(y1-y0, 2)))
    rows.sort(reverse=True)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--occ', action='store_true', help='add exact heights via pythonocc (slow on huge files)')
    args = ap.parse_args()
    sz = os.path.getsize(args.input)
    log(f"# {os.path.basename(args.input)}  ({sz/1e6:.1f} MB)\n")

    agg, refdes_prod, all_names = text_profile(args.input)
    layers, chips, tallcaps, comps = classify(agg, refdes_prod)

    def show(title, rows):
        log(f"== {title} ==")
        for nb, nm, ins, nf in sorted(rows, reverse=True)[:12]:
            log(f"  {nb/1e6:6.1f} MB  x{ins:<4d} {nf:6d} faces  {nm[:46]}")
        if not rows: log("  (none)")
        log("")
    show("STRIP - board layers (no mechanical height)", layers)
    show("STRIP - flat SMD chip passives", chips)
    show("KEEP  - tall/special caps & resistors (part-number models)", tallcaps)
    show("KEEP  - components (ICs, connectors, inductors, board, cover, ...)", comps)

    # Recommendation scans ALL product names (any nesting level), so strippable
    # detail nested inside components (e.g. BGA SOLDER_BALL) is also caught.
    layer_frags = sorted({k for k in LAYER_KEYS if any(k in n for n in all_names)})
    fam = sorted({c for c in CHIP_FOOTPRINTS if any(n.startswith(c) for n in all_names)})
    nested = sorted({n for n in all_names
                     if any(k in n for k in LAYER_KEYS)
                     and n not in {x[1] for x in layers}})
    rm = ','.join(layer_frags + fam)
    if nested:
        log(f"  note: also strippable but nested inside components: {nested}")
    log("== RECOMMENDED STRIP ==")
    log(f"  --rm-refdes \"\" --rm-product \"{rm}\"")
    strip_mb = sum(nb for nb, *_ in layers) + sum(nb for nb, *_ in chips)
    log(f"  (board layers ~{strip_mb/1e6:.0f} MB of {sz/1e6:.0f} MB; chip passives add count not size;")
    log(f"   keeps board outline + components + tall caps. verify_step.py reports the real result.)\n")

    if args.occ:
        log("== exact component heights (pythonocc XCAF) ==")
        try:
            rows = occ_heights(args.input)
            for h, nm, w, d in rows[:20]:
                log(f"  {h:7.2f} mm tall   {w:6.1f}x{d:<6.1f}  {nm[:40]}")
            log(f"  ({len(rows)} top-level components)")
        except Exception as e:
            log(f"  (pythonocc unavailable or failed: {type(e).__name__}: {e})")

if __name__ == '__main__':
    main()
