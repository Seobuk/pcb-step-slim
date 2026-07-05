<div align="center">

# 🔧 pcb-step-slim

### Slim a heavy PCB STEP assembly for fast mechanical review

Turn a hundreds-of-MB PCB STEP that **won't open** in SolidWorks (or any CAD)
into a light model that **opens in seconds** — without losing the parts that matter.

[한국어](README.md) · **English**

![license](https://img.shields.io/badge/license-MIT-green.svg)
![python](https://img.shields.io/badge/python-3.7%2B-blue.svg)
![deps](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen.svg)
![claude code skill](https://img.shields.io/badge/Claude%20Code-skill-8A2BE2.svg)

</div>

---

## ⚡ At a glance

Run on a real **3-phase driver board**:

<div align="center">

| Metric | Before | After | Reduction |
|:---|---:|---:|:---:|
| 📦 File size | 286.7 MB | **19.8 MB** | 🔻 **93%** |
| 🧊 Solids (bodies) | 5,117 | **353** | 🔻 **93%** |
| 🔲 Faces | 60,680 | **7,088** | 🔻 **88%** |

</div>

> 💡 SolidWorks import time scales with **body/face count, not file size** —
> so this is typically the difference between *"won't open"* and *"opens in seconds."*

It strips electrical & cosmetic detail (copper traces, pads, vias, soldermask,
silkscreen, BGA solder balls, flat SMD chip passives) and **keeps** the board
outline, every component, and height-driving parts (tall bulk caps, connectors,
inductors, ICs, heatsink/cover).

---

## 🧠 Why a tool (and not find-and-replace)

A STEP file isn't a parts list — it's a **graph of millions of cross-referencing
entities (`#id`)**. Delete lines by name and you get dangling references.

`strip_step.py` builds the reference graph and keeps only what's reachable from
the parts you keep (a **mark-sweep**), so the output is always —

- ✅ a **valid, reference-closed STEP**
- ✅ **exact original geometry** on what remains (no re-tessellation)
- ✅ **per-part colors** preserved

---

## 🧩 What gets removed / kept

<table>
<tr>
<th>🗑️ Strip (no mechanical height)</th>
<th>📌 Keep</th>
</tr>
<tr>
<td valign="top">

Products whose name contains:
`_copper` · `_pad` · `_via`
`_silkscreen` · `_soldermask`
`_paste` · `SOLDER_BALL`

Flat SMD chip footprints:
`C_0201/0402/0603/0805/1206`
`R_0201/0402/0603/0805/1206`

</td>
<td valign="top">

Board substrate outline (`_PCB`)

All ICs · connectors · inductors · cover

**Tall/special caps** — e.g. a bulk
MLCC like `CKG57…`

</td>
</tr>
</table>

> ⚠️ Chip passives are stripped by *footprint product name*, **not** by `C#/R#`
> reference designator — precisely so a height-critical part-numbered cap
> (e.g. `CKG57…`) is never deleted.

---

## 📦 Install

- **Required** — Python **3.7+** (standard library only; `strip_step.py` and the
  structural checks need nothing else)
- **Optional** — [`pythonocc-core`](https://github.com/tpaviot/pythonocc-core)
  (OpenCASCADE) enables exact per-component **heights** (`analyze --occ`) and a real
  *"does it load in a CAD kernel"* test (`verify`). Without it, those steps
  **degrade gracefully to text-only**.

  ```bash
  conda install -c conda-forge pythonocc-core   # in a Python 3.10/3.11 env
  ```

---

## 🚀 Usage

```bash
# 1) analyze — where the weight is + recommended strip set
python scripts/analyze_step.py board.step          # text-only, fast
python scripts/analyze_step.py board.step --occ    # + exact heights (pythonocc)

# 2) strip — apply the recommended --rm-product from step 1
python scripts/strip_step.py board.step \
  --rm-refdes "" \
  --rm-product "_copper,_pad,_via,_silkscreen,_soldermask,SOLDER_BALL,C_0402,C_0603,C_0805,C_1206,R_0402,R_0603,R_0805" \
  -o board_mechanical.step

# 3) verify — reference integrity + (with pythonocc) actually loads in OCCT
python scripts/verify_step.py board_mechanical.step
```

<details>
<summary><b>🎛️ Options in detail — <code>--rm-product</code> vs <code>--rm-refdes</code></b></summary>

<br>

| Option | Meaning |
|:---|:---|
| `--rm-product` | comma list of **PRODUCT-name substrings** to remove |
| `--rm-refdes`  | **reference-designator prefixes** matched as `^PREFIX<digits>$` (e.g. `C,R`) |

> **Prefer `--rm-product`** (footprint names) so part-numbered caps stay.
> `--rm-refdes C,R` would also delete part-number caps like `CKG57…`.

- 🎨 **Keep the green soldermask look for a presentation** → drop `_soldermask,_silkscreen` from `--rm-product`
- 🪶 **Need it even lighter** → add IC leads: `LEAD-SO,LEAD-TSSOP`

</details>

---

## 🤖 Use as a Claude Code skill

This repo is also a [Claude Code](https://claude.com/claude-code) **skill**.
Drop the folder into `~/.claude/skills/` (or a project's `.claude/skills/`) and
invoke `/pcb-step-slim`; `SKILL.md` drives the **analyze → confirm → strip → verify**
workflow.

```bash
git clone https://github.com/Seobuk/pcb-step-slim ~/.claude/skills/pcb-step-slim
```

---

## 📄 License

**MIT** — see [LICENSE](LICENSE).

<div align="center">
<sub>For every mechanical engineer who's watched a PCB STEP refuse to open 🛠️</sub>
</div>
