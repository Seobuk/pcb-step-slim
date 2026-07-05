# pcb-step-slim

**English** | [한국어](README.ko.md)

Slim down a heavy **PCB STEP/STP assembly** so it opens fast in SolidWorks (or any
CAD) for **mechanical / enclosure review** — without losing the parts that matter.

It strips non-mechanical detail (copper traces, pads, vias, soldermask, silkscreen,
BGA solder balls, flat SMD chip passives) and keeps the board outline, every
component, and height-driving parts (tall bulk caps, connectors, inductors, ICs,
heatsink/cover).

On a real 3-phase driver board:

| | before | after |
|---|---|---|
| file size | 286.7 MB | **19.8 MB** |
| solids (bodies) | 5117 | **353** |
| faces | 60 680 | **7 088** |

SolidWorks import time scales with **body/face count, not file size** — so this is
typically the difference between "won't open" and "opens in seconds."

## Why a tool (and not find-and-replace)

A STEP file is a graph of millions of cross-referencing entities (`#id`), not a
parts list. You can't delete lines by name without dangling references. `strip_step.py`
builds the reference graph and keeps only what's reachable from the parts you keep
(a mark-sweep), so the output is always a **valid, reference-closed STEP with exact
original geometry and per-part colors** preserved on what remains.

## What gets removed / kept

**Strip** (no mechanical height): products whose name contains `_copper`, `_pad`,
`_via`, `_silkscreen`, `_soldermask`, `_paste`, `SOLDER_BALL`; and flat SMD chip
footprints `C_0201/0402/0603/0805/1206`, `R_0201/0402/0603/0805/1206`.

**Keep**: board substrate outline, all ICs/connectors/inductors/cover, and
**tall/special caps** — e.g. a bulk MLCC like `CKG57…`. Note it strips chip passives
by *footprint product name*, **not** by `C#/R#` reference designator, precisely so a
height-critical part-numbered cap is not deleted.

## Install

- **Required:** Python 3.7+ (standard library only — `strip_step.py` and the
  structural checks need nothing else).
- **Optional:** [`pythonocc-core`](https://github.com/tpaviot/pythonocc-core)
  (OpenCASCADE) enables exact per-component heights (`analyze --occ`) and a real
  "does it load in a CAD kernel" test (`verify`). Without it, those steps degrade
  gracefully to text-only.

  ```bash
  conda install -c conda-forge pythonocc-core      # in a Python 3.10/3.11 env
  ```

## Usage

```bash
# 1) analyze: where the weight is + recommended strip set (+ heights with --occ)
python scripts/analyze_step.py board.step            # text-only, fast
python scripts/analyze_step.py board.step --occ      # + exact heights (pythonocc)

# 2) strip: apply (use the recommended --rm-product from step 1)
python scripts/strip_step.py board.step \
  --rm-refdes "" \
  --rm-product "_copper,_pad,_via,_silkscreen,_soldermask,SOLDER_BALL,C_0402,C_0603,C_0805,C_1206,R_0402,R_0603,R_0805" \
  -o board_mechanical.step

# 3) verify: reference integrity + (with pythonocc) actually loads in OCCT
python scripts/verify_step.py board_mechanical.step
```

`--rm-product` = comma list of PRODUCT-name substrings to remove.
`--rm-refdes`  = reference-designator prefixes matched as `^PREFIX<digits>$`
(e.g. `C,R`) — prefer `--rm-product` with footprint names so part-numbered caps stay.

Keep the green soldermask look for a presentation? Drop `_soldermask,_silkscreen`
from `--rm-product`. Need it even lighter? Add IC leads (`LEAD-SO,LEAD-TSSOP`).

## Use as a Claude Code skill

This repo is also a [Claude Code](https://claude.com/claude-code) skill. Drop the
folder into `~/.claude/skills/` (or a project's `.claude/skills/`) and invoke
`/pcb-step-slim`; `SKILL.md` drives the analyze → confirm → strip → verify workflow.

## License

MIT — see [LICENSE](LICENSE).
