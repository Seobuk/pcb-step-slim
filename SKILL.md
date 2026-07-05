---
name: pcb-step-slim
description: >-
  Slim down a heavy PCB STEP/STP assembly so it opens fast in SolidWorks (or any
  CAD) for mechanical / enclosure review. Strips non-mechanical detail — copper
  traces, pads, vias, soldermask, silkscreen, BGA solder balls, and flat SMD chip
  passives — while keeping the board outline, all components, and tall/height-
  driving parts. Use when a STEP file is too large or too slow to open, when the
  user wants to "lighten / simplify / reduce / 경량화" a PCB STEP, or to measure
  per-component heights. Reference-closed text surgery (fast, exact geometry) with
  optional OpenCASCADE (pythonocc) analysis + load verification.
---

# PCB STEP slimmer

Turns a multi-hundred-MB KiCad/OpenCASCADE PCB STEP export into a light mechanical
model. On the reference board: **286 MB → 20 MB, 5117 → 353 solids**, output still
opens in an OCCT kernel.

## Why this works
A STEP file is a graph of millions of cross-referencing entities (`#id`), not a
parts list. These scripts build the reference graph and keep only what is reachable
from the parts you keep (a mark-sweep), so the output is always a valid,
reference-closed STEP with exact original geometry and per-part colors preserved.

For mechanical review only the height/keep-out envelope matters: strip electrical &
cosmetic PCB detail (copper, pads, vias, soldermask, silkscreen, solder balls) and
flat SMD chip passives; keep the board outline, components, and tall caps.

## Python
- Text scripts (`strip_step.py`, structural part of `verify_step.py`) are pure
  stdlib — any Python 3.7+.
- OpenCASCADE features (`analyze_step.py --occ` heights, `verify_step.py` load test)
  need `pythonocc-core`. If it isn't importable, those steps degrade to text-only.
  Detect a pythonocc-capable interpreter (a conda env with `pythonocc-core`); use
  plain `python` otherwise.

## Workflow
Let `SK = scripts` (relative to this skill). Always keep the original file.

1. **Analyze** — find the weight and get a recommended strip set:
   ```
   <occ-python-or-python> SK/analyze_step.py "INPUT.step" [--occ]
   ```
   Prints STRIP groups (board layers, chip passives), KEEP groups (tall caps,
   components), a "nested strippable" note (e.g. BGA `SOLDER_BALL`), and a
   ready-to-use `--rm-refdes/--rm-product` line. `--occ` adds exact heights but is
   slow + RAM-heavy on >100 MB files.

2. **Confirm with the user.** Show the STRIP/KEEP breakdown and the recommended
   command. Ask before removing anything they might need (tall electrolytics, a
   specific connector). Defaults keep tall caps and all components.

3. **Strip:**
   ```
   <python> SK/strip_step.py "INPUT.step" --rm-refdes "" \
     --rm-product "<recommended list>" -o "INPUT_mechanical.step"
   ```
   Prefer `--rm-product` with footprint names over `--rm-refdes C,R` — the latter
   also deletes part-number caps (e.g. `CKG57…`) that must stay.

4. **Verify:**
   ```
   <occ-python-or-python> SK/verify_step.py "INPUT_mechanical.step"
   ```
   Expect `dangling refs: 0`, `VALID`, and (with pythonocc) `OCC load: OK — N bodies`.

5. **Report** before/after size, solids, faces, and what was kept/removed.

## Gotchas
- NAUO and PRODUCT entities can span multiple lines — scripts parse the reference
  graph, not line patterns, so this is handled (a naive grep misses them).
- A few removed parts may leave an empty PRODUCT metadata entry if a `SHAPE_ASPECT`
  references them — harmless (no geometry, no body); output stays valid.
