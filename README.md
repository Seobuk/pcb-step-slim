<div align="center">

# 🔧 pcb-step-slim

### 무거운 PCB STEP 어셈블리를 기구 검토용으로 가볍게

SolidWorks(또는 모든 CAD)에서 **안 열리던** 수백 MB짜리 PCB STEP을
**몇 초 만에 열리는** 경량 모델로 — 정작 중요한 부품은 하나도 잃지 않으면서.

**한국어** · [English](README.en.md)

![license](https://img.shields.io/badge/license-MIT-green.svg)
![python](https://img.shields.io/badge/python-3.7%2B-blue.svg)
![deps](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen.svg)
![claude code skill](https://img.shields.io/badge/Claude%20Code-skill-8A2BE2.svg)

</div>

---

## ⚡ 한눈에

실제 **3상 드라이버 보드**로 돌린 결과:

<div align="center">

| 항목 | 변경 전 | 변경 후 | 감소 |
|:---|---:|---:|:---:|
| 📦 파일 크기 | 286.7 MB | **19.8 MB** | 🔻 **93%** |
| 🧊 솔리드(바디) | 5,117 | **353** | 🔻 **93%** |
| 🔲 면(faces) | 60,680 | **7,088** | 🔻 **88%** |

</div>

> 💡 SolidWorks 임포트 시간은 **파일 크기가 아니라 바디/면 개수**에 좌우됩니다.
> 그래서 보통 *"안 열림"* 과 *"몇 초 만에 열림"* 의 차이를 만듭니다.

전기적·외관용 디테일(동박 트레이스, 패드, via, 솔더마스크, 실크스크린, BGA 솔더볼,
납작한 SMD 칩 패시브)을 제거하고 — **보드 외형 + 모든 부품 + 높이를 좌우하는 부품**
(키 큰 벌크 캡, 커넥터, 인덕터, IC, 방열판/커버)은 **그대로** 둡니다.

---

## 🧠 왜 단순 찾기-바꾸기가 아니라 도구인가

STEP 파일은 부품 목록이 아니라 **수백만 개의 엔티티(`#id`)가 서로 참조하는 그래프**입니다.
이름으로 줄을 지우면 참조가 깨집니다(dangling).

`strip_step.py`는 참조 그래프를 만들어 **남길 부품에서 도달 가능한 것만** 보존하는
**mark-sweep** 방식이라, 결과는 항상 —

- ✅ **유효하고 참조가 닫힌(reference-closed) STEP**
- ✅ 남는 부품의 **정확한 원본 형상**(re-tessellation 없음)
- ✅ **부품별 색상** 보존

---

## 🧩 무엇을 제거하고 무엇을 남기나

<table>
<tr>
<th>🗑️ 제거 (기계적 높이 없음)</th>
<th>📌 보존</th>
</tr>
<tr>
<td valign="top">

제품명에 다음이 포함된 것:
`_copper` · `_pad` · `_via`
`_silkscreen` · `_soldermask`
`_paste` · `SOLDER_BALL`

납작한 SMD 칩 풋프린트:
`C_0201/0402/0603/0805/1206`
`R_0201/0402/0603/0805/1206`

</td>
<td valign="top">

보드 기판 외형(`_PCB`)

모든 IC · 커넥터 · 인덕터 · 커버

**키 큰/특수 캡** — 예: `CKG57…`
같은 벌크 MLCC

</td>
</tr>
</table>

> ⚠️ 칩 패시브를 `C#/R#` **레퍼런스 지정자**가 아니라 *풋프린트 제품명*으로 제거합니다.
> 높이가 중요한 **부품번호 캡**(예: `CKG57…`)이 실수로 삭제되지 않도록 하기 위함입니다.

---

## 📦 설치

- **필수** — Python **3.7+** (표준 라이브러리만. `strip_step.py`와 구조 검사는 추가 설치 불필요)
- **선택** — [`pythonocc-core`](https://github.com/tpaviot/pythonocc-core) (OpenCASCADE)
  가 있으면 부품별 **정확한 높이**(`analyze --occ`)와 *"실제 CAD 커널에서 열리는지"* 테스트(`verify`)가
  가능합니다. 없으면 해당 단계는 **텍스트 전용으로 자동 폴백**됩니다.

  ```bash
  conda install -c conda-forge pythonocc-core   # Python 3.10/3.11 환경에서
  ```

---

## 🚀 사용법

```bash
# 1) 분석 — 무게가 어디 몰렸는지 + 추천 제거 세트
python scripts/analyze_step.py board.step          # 텍스트 전용, 빠름
python scripts/analyze_step.py board.step --occ    # + 정확한 높이 (pythonocc)

# 2) 제거 — 1단계에서 추천된 --rm-product 그대로 적용
python scripts/strip_step.py board.step \
  --rm-refdes "" \
  --rm-product "_copper,_pad,_via,_silkscreen,_soldermask,SOLDER_BALL,C_0402,C_0603,C_0805,C_1206,R_0402,R_0603,R_0805" \
  -o board_mechanical.step

# 3) 검증 — 참조 무결성 + (pythonocc 있으면) 실제 OCCT 로딩
python scripts/verify_step.py board_mechanical.step
```

<details>
<summary><b>🎛️ 옵션 자세히 — <code>--rm-product</code> vs <code>--rm-refdes</code></b></summary>

<br>

| 옵션 | 의미 |
|:---|:---|
| `--rm-product` | 제거할 **PRODUCT 이름 부분문자열**의 콤마 목록 |
| `--rm-refdes`  | `^접두사<숫자>$`로 매칭되는 **레퍼런스 지정자 접두사**(예: `C,R`) |

> 부품번호 캡이 남도록 **가급적 `--rm-product`(풋프린트 이름)** 를 쓰세요.
> `--rm-refdes C,R`은 `CKG57…` 같은 부품번호 캡까지 지워버립니다.

- 🎨 **발표용으로 녹색 솔더마스크 외관을 남기려면** → `--rm-product`에서 `_soldermask,_silkscreen` 제거
- 🪶 **더 가볍게 하려면** → IC 리드 추가: `LEAD-SO,LEAD-TSSOP`

</details>

---

## 🤖 Claude Code 스킬로 사용

이 저장소는 [Claude Code](https://claude.com/claude-code) **스킬**이기도 합니다.
폴더를 `~/.claude/skills/`(또는 프로젝트의 `.claude/skills/`)에 넣고 `/pcb-step-slim`을
호출하면, `SKILL.md`가 **분석 → 확인 → 제거 → 검증** 워크플로를 안내합니다.

```bash
git clone https://github.com/Seobuk/pcb-step-slim ~/.claude/skills/pcb-step-slim
```

---

## 📄 라이선스

**MIT** — [LICENSE](LICENSE) 참고.

<div align="center">
<sub>PCB STEP이 안 열려서 답답했던 모든 기구 엔지니어를 위해 🛠️</sub>
</div>
