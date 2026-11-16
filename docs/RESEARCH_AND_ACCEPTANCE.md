# 연구·팀 배포 완료 조건

## WHY: 단순 변조 전파와 검증 기능을 분리

공격자가 작성한 값을 모든 단계가 신뢰하도록 만든 뒤 `에너지 × 단가`가 바뀌는 것은 구현 확인이지, 그 자체로 새로운 취약점 입증은 아닙니다. 본 패키지의 Mock Billing은 **결과를 수량화하는 실험 도구**입니다. 상용 eMSP에 대한 취약성 결론을 대신하지 않습니다.

연구의 비교 대상은 각 신뢰 경계의 실제 동작입니다.

- EVerest/OCPP에서 값·단위·거래 연결이 어떻게 검증되는가?
- CitrineOS가 최종 CDR을 어떤 meter 샘플/누적값으로 만드는가?
- eMSP mock의 검증 finding이 단순 기록인지 실제 거부인지?
- Billing의 중복·거래·계약 검사가 실제 차단에 영향을 주는가?
- 정상 형식으로 일관되게 조작된 값은 여전히 참값을 보장하지 못한다는 한계는 무엇인가?

## HOW: 완료 게이트

| 단계 | 성공 증거 | 아직 성공이 아닌 경우 |
|---|---|---|
| G0 기존 환경 진단 | 실제 EVerest commit/image digest/config 경로 기록 | 예전 대화에 언급된 버전만 인용 |
| G1 소프트웨어 기동 | Core/DB/RabbitMQ/Hasura/OCPI/mock/Billing 상태 확인 | compose 파일만 작성 |
| G2 OCPP 2.0.1 | 올바른 station의 BootNotification 수락, 정상 TransactionEvent 저장 | TCP 접속만 확인, OCPP 2.1로 실행 |
| G3 PnC | 실제 ISO 15118-2 계약 인증 성공과 계정 연결 | RFID·인증 생략·remote start만 성공 |
| G4 CDR 전파 | 정상 세션 종료 → OCPI CDR POST → mock의 수신 원문·응답 | DB에 수동 넣은 CDR 또는 fixture POST |
| G5 청구액 계산 | 실제 수신 CDR hash·계약·단가 snapshot·청구 명세 연결 | CDR 수신만 됨, 가격 정책 미확정 |
| G6 팀 재현 | 다른 팀원의 깨끗한 checkout에서 G1~G5 재현 | 작성자 PC에서만 동작 |

## WHAT: 실험별 수집 항목

```text
run_id / scenario / source commit / image identities
PnC 인증 결과·계약 연결
station_id / OCPP transactionId / OCPI session_id / CDR id
변조 전 SIL 기준 에너지 (변조 경로 밖에서 별도 기록)
OCPP 시작·종료 누적 계량값, unit, multiplier
CDR total_energy[kWh] 및 total_cost (CPO 비용)
eMSP 수신 HTTP/OCPI 응답 + validation findings
소매 요금 policy snapshot / invoice_id / 최종 계산액 / 보류 이유
```

누적 계량값은 시작·종료 차이를 사용합니다. 중간 누적값들을 합산하지 않습니다. Wh↔kWh 변환 및 OCPP 단위·multiplier를 명시합니다. 이 패키지는 OCPP 계량값을 CDR로 바꾸는 변환기를 임의로 다시 구현하지 않았으며 그 기능은 공식 Core/OCPI에서 관측해야 합니다.

## 최소 실험 세트

1. 정상 PnC 세션: 모든 단계가 같은 거래를 가리키는지 확인.
2. EVerest의 계량 보고 경로에서 과소/과대 보고: SIL 기준값은 불변으로 보존.
3. 같은 CDR 재전송: 수신 횟수와 청구 횟수를 별도로 확인.
4. 같은 CDR ID의 내용 변경: upstream mock 동작과 Billing 보류를 구분.
5. 다른 계약/세션 식별자: 어느 경계가 잘못된 귀속을 거부하는지 확인.

위 실험은 본 패키지에서 자동 수행하지 않았습니다. `billing.demo`는 청구 모듈의 합성 입력 테스트입니다.

## Mock 검증을 과대 해석하지 않기

검토한 upstream `apps/mock-msp/src/modules/cdrs.ts`는 schema-invalid 데이터도 finding을 남기면서 저장할 수 있고 ID 기준 upsert를 합니다. 따라서 'eMSP에서 validation 기능이 있다'와 '오류 CDR을 거부한다'는 다릅니다.

본 Billing은 수신 CDR 상태를 읽어 별도 정책으로 invoice를 만들거나 보류합니다. 이 보류는 **우리 추가 모듈의 정책 효과**이지 CitrineOS/실제 eMSP의 기본 방어로 보고하면 안 됩니다.

`/_mock/state/cdrs`는 현재 상태 스냅샷이므로 polling 사이에 덮어쓴 모든 요청을 보존하지 않습니다. 중복·충돌 전파 연구에는 `/_mock/received/cdrs` 원문 trace를 별도로 수집해야 합니다. 레코더 최대 보존량/페이지 제한을 확인하고 세션별로 저장합니다.

## 결제/영수증의 명칭

본 출력: 모의 고객 청구 명세 (`SIMULATED_INVOICE_NOT_PAID`).

구현 안 함: Stripe 승인, 자금 이동, 유료 영수증, 세금계산서, 금융 정산. 추후 테스트 PG를 붙이더라도 API 요청 생성과 결제 성공 webhook을 구분해야 합니다. 결제 성공 상태를 계량값 진위 증거로 사용할 수 없습니다.

## 향후 선택 확장

CitrineOS Payment/Stripe는 기본 환경에서 제외합니다. 목적이 PG 테스트라면 현재 Core API/RabbitMQ 이벤트/DB와의 호환성부터 확인하고 별도 profile로 붙입니다. eMSP가 없는 CPO 직접 결제 시연은 로밍 eMSP 청구 실험과 다른 경로로 기록합니다.
