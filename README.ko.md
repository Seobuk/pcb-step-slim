# pcb-step-slim

[English](README.md) | **한국어**

무거운 **PCB STEP/STP 어셈블리**를 가볍게 만들어 SolidWorks(또는 모든 CAD)에서
**기구/케이스 검토**용으로 빠르게 열리게 합니다 — 정작 중요한 부품은 잃지 않으면서요.

전기적·외관용 디테일(동박 트레이스, 패드, via, 솔더마스크, 실크스크린, BGA 솔더볼,
납작한 SMD 칩 패시브)을 제거하고, **보드 외형 + 모든 부품 + 높이를 좌우하는 부품**
(키 큰 벌크 캡, 커넥터, 인덕터, IC, 방열판/커버)은 그대로 둡니다.

실제 3상 드라이버 보드 기준:

| | 변경 전 | 변경 후 |
|---|---|---|
| 파일 크기 | 286.7 MB | **19.8 MB** |
| 솔리드(바디) | 5117 | **353** |
| 면(faces) | 60,680 | **7,088** |

SolidWorks 임포트 시간은 **파일 크기가 아니라 바디/면 개수**에 좌우됩니다 — 그래서 보통
"안 열림"과 "몇 초 만에 열림"의 차이를 만듭니다.

## 왜 단순 찾기-바꾸기가 아니라 도구인가

STEP 파일은 부품 목록이 아니라 수백만 개의 엔티티(`#id`)가 서로 참조하는 그래프입니다.
이름으로 줄을 지우면 참조가 깨집니다(dangling). `strip_step.py`는 참조 그래프를 만들어
**남길 부품에서 도달 가능한 것만** 보존하는 mark-sweep 방식이라, 결과는 항상
**유효하고 참조가 닫힌(reference-closed) STEP**이며, 남는 부품의 **정확한 원본 형상과
부품별 색상**이 보존됩니다.

## 무엇을 제거하고 무엇을 남기나

**제거** (기계적 높이 없음): 제품명에 `_copper`, `_pad`, `_via`, `_silkscreen`,
`_soldermask`, `_paste`, `SOLDER_BALL`이 포함된 것 + 납작한 SMD 칩 풋프린트
`C_0201/0402/0603/0805/1206`, `R_0201/0402/0603/0805/1206`.

**보존**: 보드 기판 외형, 모든 IC/커넥터/인덕터/커버, 그리고 **키 큰/특수 캡** —
예: `CKG57…` 같은 벌크 MLCC. 칩 패시브를 `C#/R#` 레퍼런스 지정자가 아니라
*풋프린트 제품명*으로 제거하는 이유가 바로 이것 — 높이가 중요한 부품번호 캡이
삭제되지 않도록 하기 위함입니다.

## 설치

- **필수:** Python 3.7+ (표준 라이브러리만 — `strip_step.py`와 구조 검사는 추가 설치 불필요).
- **선택:** [`pythonocc-core`](https://github.com/tpaviot/pythonocc-core)
  (OpenCASCADE)가 있으면 부품별 정확한 높이(`analyze --occ`)와 "실제 CAD 커널에서
  열리는지" 테스트(`verify`)가 가능합니다. 없으면 해당 단계는 텍스트 전용으로 폴백됩니다.

  ```bash
  conda install -c conda-forge pythonocc-core      # Python 3.10/3.11 환경에서
  ```

## 사용법

```bash
# 1) 분석: 무게가 어디 몰렸는지 + 추천 제거 세트 (--occ로 높이까지)
python scripts/analyze_step.py board.step            # 텍스트 전용, 빠름
python scripts/analyze_step.py board.step --occ      # + 정확한 높이 (pythonocc)

# 2) 제거: 적용 (1단계에서 추천된 --rm-product 사용)
python scripts/strip_step.py board.step \
  --rm-refdes "" \
  --rm-product "_copper,_pad,_via,_silkscreen,_soldermask,SOLDER_BALL,C_0402,C_0603,C_0805,C_1206,R_0402,R_0603,R_0805" \
  -o board_mechanical.step

# 3) 검증: 참조 무결성 + (pythonocc 있으면) 실제 OCCT 로딩
python scripts/verify_step.py board_mechanical.step
```

`--rm-product` = 제거할 PRODUCT 이름 부분문자열의 콤마 목록.
`--rm-refdes`  = `^접두사<숫자>$`로 매칭되는 레퍼런스 지정자 접두사(예: `C,R`) —
부품번호 캡이 남도록 가급적 풋프린트 이름의 `--rm-product`를 쓰세요.

발표용으로 녹색 솔더마스크 외관을 남기고 싶다면 `--rm-product`에서
`_soldermask,_silkscreen`을 빼세요. 더 가볍게 하려면 IC 리드(`LEAD-SO,LEAD-TSSOP`)를 추가하세요.

## Claude Code 스킬로 사용

이 저장소는 [Claude Code](https://claude.com/claude-code) 스킬이기도 합니다. 폴더를
`~/.claude/skills/`(또는 프로젝트의 `.claude/skills/`)에 넣고 `/pcb-step-slim`을
호출하면, `SKILL.md`가 분석 → 확인 → 제거 → 검증 워크플로를 안내합니다.

## 라이선스

MIT — [LICENSE](LICENSE) 참고.
