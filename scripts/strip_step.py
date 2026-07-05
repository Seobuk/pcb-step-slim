#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strip capacitors (C*), resistors (R*) and the via body from an OpenCASCADE
AP214 STEP assembly, then write a new valid STEP file.

Pure standard-library. Operates on the raw STEP text via a reference-closed
mark-sweep, so geometry precision and per-part colours are preserved for the
parts that stay.

    python strip_components.py INPUT.step                 # dry-run report only
    python strip_components.py INPUT.step -o OUT.step      # apply + write
"""
import re, sys, os, argparse, array

ENT_RE = re.compile(rb'^\s*#(\d+)\s*=\s*(.*)$', re.S)
REF_RE = re.compile(rb'#(\d+)')

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def log(*a):
    print(*a, flush=True)

def parse(path):
    with open(path, 'rb') as f:
        data = f.read()
    log(f"read {len(data):,} bytes")
    ds = data.find(b'DATA;')
    de = data.rfind(b'ENDSEC;')
    header = data[:ds + len(b'DATA;')]
    footer = data[de:]
    body = data[ds + len(b'DATA;'):de]
    n_defs = len(re.findall(rb'#\d+\s*=', body))   # expected entity count
    text, order, max_id = {}, [], 0
    for stmt in body.split(b';'):
        m = ENT_RE.match(stmt)
        if not m:
            continue
        i = int(m.group(1))
        text[i] = m.group(2).strip()              # body only, no "#id ="
        order.append(i)
        if i > max_id:
            max_id = i
    log(f"parsed {len(text):,} entities (expected {n_defs:,}), max id #{max_id:,}")
    if len(text) != n_defs:
        log(f"  !! WARNING: parsed count != expected ({n_defs-len(text):,} diff) "
            f"-- a string may contain ';'. Aborting to be safe.")
        sys.exit(2)
    return header, footer, order, text, max_id

def etype(s):
    if s.startswith(b'('):
        return b'('
    m = re.match(rb'[A-Z_0-9]+', s)
    return m.group(0) if m else b''

def main():
    ap = argparse.ArgumentParser(
        description="Strip sub-trees from an OpenCASCADE STEP assembly by "
                    "reference-designator prefix and/or product-name substring.")
    ap.add_argument('input')
    ap.add_argument('-o', '--output', default=None)
    ap.add_argument('--rm-refdes', default='C,R',
                    help="comma list of refdes prefixes to remove, matched as "
                         "^PREFIX<digits>$ (default 'C,R'; '' to disable)")
    ap.add_argument('--rm-product', default='_via',
                    help="comma list of substrings; remove any part whose PRODUCT "
                         "name contains one (default '_via')")
    args = ap.parse_args()

    header, footer, order, text, max_id = parse(args.input)

    # quoted-string extractor ('' is an escaped quote inside a STEP string)
    QSTR_RE = re.compile(rb"'((?:[^']|'')*)'")

    # ---- NAUOs --------------------------------------------------------------
    # Whitespace/line-break tolerant: refdes = 2nd quoted string;
    # the two PD refs = first two '#' references (relating, related).
    nauo = {}   # id -> (refdes, parent_pd, child_pd)
    for i, s in text.items():
        if s.startswith(b'NEXT_ASSEMBLY_USAGE_OCCURRENCE'):
            strs = QSTR_RE.findall(s)
            refs = REF_RE.findall(s)
            if len(strs) >= 2 and len(refs) >= 2:
                nauo[i] = (strs[1].decode('latin-1'), int(refs[0]), int(refs[1]))

    # ---- product / pd maps (robust to line breaks) -------------------------
    pd_formation, formation_product, product_name = {}, {}, {}
    for i, s in text.items():
        if s.startswith(b'PRODUCT_DEFINITION('):          # PD('design','',#formation,#ctx)
            r = REF_RE.findall(s)
            if r: pd_formation[i] = int(r[0])
        elif s.startswith(b'PRODUCT_DEFINITION_FORMATION('):  # PDF('','',#product)
            r = REF_RE.findall(s)
            if r: formation_product[i] = int(r[0])
        elif s.startswith(b'PRODUCT('):                   # PRODUCT('name',...)
            m = QSTR_RE.search(s)
            if m: product_name[i] = m.group(1).decode('latin-1')

    def pd_product(pd):
        f = pd_formation.get(pd)
        return formation_product.get(f) if f is not None else None

    # ---- removal targets ----------------------------------------------------
    prefixes = tuple(x for x in args.rm_refdes.split(',') if x)
    substrs  = tuple(x for x in args.rm_product.split(',') if x)
    ref_re = re.compile('^(' + '|'.join(re.escape(p) for p in prefixes) + r')\d+$') \
             if prefixes else None
    removed_occ_nauos, removed_pd_roots = set(), set()
    refdes_n = {p: 0 for p in prefixes}
    borderline = {}
    for i, (refdes, ppd, cpd) in nauo.items():
        if ref_re and ref_re.match(refdes):
            removed_occ_nauos.add(i); removed_pd_roots.add(cpd)
            refdes_n[refdes[0]] = refdes_n.get(refdes[0], 0) + 1
        elif refdes and prefixes and refdes[0] in ''.join(prefixes):
            borderline[refdes] = borderline.get(refdes, 0) + 1

    target_products = {p for p, n in product_name.items()
                       if any(x in n for x in substrs)}
    target_pds = {pd for pd in pd_formation if pd_product(pd) in target_products}
    prod_n = 0
    for i, (refdes, ppd, cpd) in nauo.items():
        if cpd in target_pds:
            removed_occ_nauos.add(i); removed_pd_roots.add(cpd); prod_n += 1

    # transitive subtree closure (sub-assemblies under a removed part)
    children, child_nauos = {}, {}
    for i, (refdes, ppd, cpd) in nauo.items():
        children.setdefault(ppd, []).append((i, cpd))
        child_nauos.setdefault(cpd, []).append(i)
    removed_pds = set()
    stack = list(removed_pd_roots)
    while stack:
        pd = stack.pop()
        if pd in removed_pds: continue
        removed_pds.add(pd)
        for (ni, cpd) in children.get(pd, []):
            removed_occ_nauos.add(ni)
            if cpd not in removed_pds: stack.append(cpd)

    def_removed_pds = {pd for pd in removed_pds
                       if child_nauos.get(pd) and all(o in removed_occ_nauos for o in child_nauos[pd])}
    removed_products = {pd_product(pd) for pd in def_removed_pds}
    removed_products.discard(None)

    log("\n=== removal targets ===")
    log(f"  refdes prefixes {list(prefixes)}: {dict(refdes_n)}")
    log(f"  product matches {list(substrs)}: {sorted({product_name[p] for p in target_products})} ({prod_n} occ)")
    log(f"  removed occurrences : {len(removed_occ_nauos)} NAUOs")
    log(f"  removed PD subtrees : {len(removed_pds)} (definitions dropped: {len(def_removed_pds)})")
    if borderline:
        log(f"  NOT removed (borderline, kept): {borderline}")

    # ---- roots (in-degree 0) -----------------------------------------------
    indeg = array.array('i', bytes(4 * (max_id + 1)))
    for s in text.values():
        for r in REF_RE.findall(s):
            r = int(r)
            if r <= max_id: indeg[r] += 1
    roots = [i for i in order if indeg[i] == 0]

    mdgpr_roots, keep_seeds, dropped_roots = [], [], 0
    for i in roots:
        s = text[i]; t = etype(s)
        if t == b'SHAPE_DEFINITION_REPRESENTATION':
            # SDR(#pds,#rep): pds is either a definition-PDS (-> PD) or a
            # 'Placement' PDS (-> NAUO). Drop if that target is being removed.
            rr = [int(x) for x in REF_RE.findall(s)]
            tgt = None
            if rr:
                pr = REF_RE.findall(text.get(rr[0], b''))
                if pr: tgt = int(pr[-1])
            if tgt in def_removed_pds or tgt in removed_occ_nauos:
                dropped_roots += 1; continue
            keep_seeds.append(i)
        elif t == b'CONTEXT_DEPENDENT_SHAPE_REPRESENTATION':
            rr = [int(x) for x in REF_RE.findall(s)]
            nau = None
            if len(rr) >= 2:
                pr = REF_RE.findall(text.get(rr[1], b''))
                if pr: nau = int(pr[-1])
            if nau in removed_occ_nauos: dropped_roots += 1; continue
            keep_seeds.append(i)
        elif t == b'MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION':
            mdgpr_roots.append(i)
        elif t == b'PRODUCT_RELATED_PRODUCT_CATEGORY':
            rr = [int(x) for x in REF_RE.findall(s)]
            if rr and rr[-1] in removed_products: dropped_roots += 1; continue
            keep_seeds.append(i)
        else:
            keep_seeds.append(i)
    log(f"\n{len(roots):,} roots | keep-seed {len(keep_seeds):,} | "
        f"MDGPR deferred {len(mdgpr_roots):,} | dropped roots {dropped_roots:,}")

    # ---- mark-sweep ---------------------------------------------------------
    visited = bytearray(max_id + 1)
    stk = []
    for i in keep_seeds:
        if not visited[i]: visited[i] = 1; stk.append(i)
    def bfs():
        while stk:
            i = stk.pop()
            s = text.get(i)
            if not s: continue
            for r in REF_RE.findall(s):
                r = int(r)
                if r <= max_id and not visited[r] and r in text:
                    visited[r] = 1; stk.append(r)
    bfs()

    # MDGPR: keep only those whose styled target survived
    kept_mdgpr = 0
    for i in mdgpr_roots:
        keep = False
        for it in (int(x) for x in REF_RE.findall(text[i])):
            sit = text.get(it, b'')
            if sit.startswith(b'STYLED_ITEM'):
                tr = REF_RE.findall(sit)
                if tr and visited[int(tr[-1])]: keep = True; break
        if keep:
            kept_mdgpr += 1
            if not visited[i]: visited[i] = 1; stk.append(i)
    bfs()

    kept = sum(1 for i in order if visited[i])
    log(f"\n=== result ===")
    log(f"  entities total : {len(order):,}")
    log(f"  kept           : {kept:,}")
    log(f"  removed        : {len(order) - kept:,}")
    log(f"  MDGPR kept     : {kept_mdgpr:,}/{len(mdgpr_roots):,}")

    if not args.output:
        log("\n(dry-run only; pass -o OUT.step to write)")
        return

    log(f"\nwriting {args.output} ...")
    with open(args.output, 'wb') as f:
        f.write(header); f.write(b'\n')
        for i in order:
            if visited[i]:
                f.write(b'#%d = ' % i); f.write(text[i]); f.write(b';\n')
        if not footer.rstrip().endswith(b'END-ISO-10303-21;'):
            f.write(footer)
            f.write(b'\nEND-ISO-10303-21;\n')
        else:
            f.write(footer)
    sz = os.path.getsize(args.output)
    log(f"done: {sz:,} bytes ({sz/1e6:.1f} MB)")

if __name__ == '__main__':
    main()
