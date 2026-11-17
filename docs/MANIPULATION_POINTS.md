# M1~M4 변조 지점 — 오픈소스에서 무엇을 바꾸면 청구가 낮아지는가

전제: 과금은 **에너지값 × 요율**이고, Billing 엔진은 받은 CDR의 `total_energy`만 쓴다
(참 충전량은 입력이 아님). 따라서 아래 "에너지가 흐르는 단일 경로"의 **어느 노드에서든
kWh를 낮추면 하류로 전파되어 청구서가 작아진다.** 지점(M1~M4)이 다른 건 변조 위치와
탐지 경계일 뿐, "값이 싸진다"는 결과는 공통이다.

## 에너지가 흐르는 단일 경로 (golden thread)

```
EVerest YetiSimulator · powermeter            (전력/계량 생성)   ← M1
   │  energy_Wh.total (MQTT publish)
   ▼
OCPP 2.0.1 TransactionEventRequest            (전송)             ← M2
   │  meterValue[].sampledValue[]  (measurand = Energy.Active.Import.Register)
   ▼
CitrineOS  MeterValueUtils.getTotalKwh()      (서버 저장·집계)   ← M3
   │  transaction.totalKwh = 마지막 Register − meterStart
   │  packages/base/src/util/meter-value-utils.ts  (호출: dal/.../transaction-event.ts:368)
   ▼
OCPI  session.kwh = transaction.totalKwh       (세션 매핑)
   │  packages/ocpi/src/mappers/session-mapper.ts:173,264
   ▼
OCPI  CDR.total_energy = session.kwh           (CDR 변환·전송)   ← M4
   │  packages/ocpi/src/mappers/cdr-mapper.ts:129
   ▼
mock eMSP → Billing  invoice = total_energy × rate
   billing/engine.py  (energy_kwh × rate_per_kwh, ROUND_HALF_UP)
```

## 지점별 — 무엇을, 어떻게, 왜 싸지나

### M1 · 계량 생성 조작
- **대상(오픈소스):** EVerest `YetiSimulator` 모듈의 `powermeter` 구현
  (strict YAML `yeti_driver_1` → `powermeter`; 실제 코드는 everest-core C++).
- **무엇을:** powermeter가 발행하는 누적 에너지 `energy_Wh.total`(또는 시뮬레이션 전력).
- **어떻게:** 보고 에너지를 예: ×0.1로 축소하거나 더 낮은 전력을 생성하도록 수정.
- **왜 싸지나:** 측정 자체가 낮게 생성 → OCPP·DB·CDR·청구서가 **전부 일치한 채로** 낮아짐.
- **탐지 경계:** SIL 기준값 ↔ EVerest 계량 로그. **프로토콜 계층끼린 전부 일치**하므로
  변조 경로 밖 독립 기준값 없이는 데이터만으로 탐지 불가 → 가장 위험·가장 어려움.
- **실행:** 현재 EVerest는 고정 이미지 → **실험용 이미지 재빌드** 필요(컨테이너 내부 임시수정은 재생성 시 소멸).

### M2 · OCPP 전송 조작
- **대상:** EVerest ↔ `citrine:8081` 사이 OCPP 2.0.1 WebSocket.
- **무엇을:** `TransactionEventRequest.meterValue[].sampledValue[]` 중
  `measurand = Energy.Active.Import.Register` 값.
- **어떻게:** 중간 **WebSocket proxy**를 두고 해당 sampledValue.value를 축소해 전달.
- **왜 싸지나:** 서버가 받는 계량값이 낮아짐 → `getTotalKwh`가 낮게 집계 → 하류 전파.
- **탐지 경계:** EVerest meterValue(원본 로그) ↔ CSMS 저장값.
- **실행:** citrineos 소스 변경 없음. **MITM proxy 직접 구현** 필요(현재 미구현).

### M3 · CSMS 처리·저장 조작
- **대상(오픈소스):** `packages/base/src/util/meter-value-utils.ts` → `getTotalKwh()`
  (register 경로: `return sorted[last] − meterStart`). 호출부
  `packages/dal/src/repositories/sequelize/transaction-event.ts:368`에서 `transaction.totalKwh`에 저장.
- **무엇을:** `getTotalKwh`의 반환값, 또는 `totalKwh` 저장값.
- **어떻게:** 반환을 `* 0.1` 하거나, meterStart를 부풀려 차이를 축소, 또는 저장 직전 totalKwh를 낮춤.
- **왜 싸지나:** 서버 DB에 저장되는 거래 에너지가 낮아짐 → `session.kwh`·CDR·청구서로 전파.
- **탐지 경계:** 수신 OCPP 이벤트(원본 meterValue) ↔ CitrineOS 거래 저장값(totalKwh).
- **실행:** vendor 소스 패치 후 `citrine` 이미지 재빌드(`scripts/stack.sh up`), vendor diff 보존.

### M4 · CDR 변환·전송 조작
- **대상(오픈소스):** `packages/ocpi/src/mappers/cdr-mapper.ts:129` `total_energy: session.kwh`.
- **무엇을:** CDR의 `total_energy`(및 선택적으로 `cdr-cost.ts`의 energy cost).
- **어떻게:** `total_energy: session.kwh` → `total_energy: session.kwh * 0.1` (또는 고정 저값).
- **왜 싸지나:** Billing 엔진이 CDR `total_energy`를 그대로 요율에 곱함 → 청구 직접 축소.
- **탐지 경계:** CitrineOS DB 거래값(totalKwh) ↔ OCPI `total_energy`.
- **실행:** 한 줄 수정 후 `ocpi` 이미지 재빌드. **가장 쉬운 실행 지점.** vendor diff 보존.

## 공통

- 한 번에 한 지점만 변경하고, **변조 경로 밖 SIL 기준값을 먼저 별도 기록**한다.
- 탐지는 단일 계층 값이 아니라 **계층 간 kWh 교차대조**로 한다(위 "탐지 경계").
- 수정은 커밋하지 말고 working-tree 패치 + `git -C vendor/citrineos-core diff`로 증거 보존,
  실험 후 `git checkout --`로 원복한다(저장소 가드레일: 고정 커밋·이미지 유지).
- 이 경로의 금액 계산은 실제 `billing/engine.py`지만 청구서는 `SIMULATED_INVOICE_NOT_PAID`
  모의 명세다. 실제 결제·물리 계량·계량 서명은 포함하지 않는다.
