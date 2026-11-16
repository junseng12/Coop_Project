# 최종 환경 목표·구현 현황·수동 검증 요약

기준일: 2026-11-16. 현재 설정 파일과 이 PC에서 성공한 새 세션의 증거를 기준으로 작성했습니다.

**현재 결론:** 이 PC에서 `/home/hyebin` 경로 없이 **Virtual EV → EVerest → CitrineOS → OCPI → mock eMSP → 모의 청구**를 재실행하고 연결을 검증했습니다. 다른 PC의 신규 설치와 실제 결제까지 완료한 환경은 아닙니다.

## 1. 최종 환경설정 목표

실제 차량 없이 소프트웨어 충전 세션을 만들고, 계약 인증·충전 거래·과금 근거·모의 청구 명세를 **같은 거래로 끝까지 추적할 수 있는 실험 환경**을 구성하는 것입니다.

| 목표 | 실제 구현·확인 결과 | 판정 |
|---|---|---|
| 기존 실험 자산 보존 | 기존 컨테이너와 DB를 삭제하지 않고 로컬 EVerest 프로젝트를 별도로 구성 | 구현 |
| 개인 홈 경로 의존 제거 | 실행에 `/home/hyebin` 불필요. 작업 폴더 내부 Compose·스크립트 사용 | 이 PC에서 재실행 확인 |
| PnC 계약 인증 | ISO 15118-2 계약 인증서 체인 검증 활성화, eMAID와 인증서 상태 수락 확인 | 새 세션에서 확인 |
| OCPP 2.0.1 충전기 연동 | `cp001` 연결·BootNotification 수락, Started/Updated/Ended 기록 | 확인 |
| OCPI 2.2.1 CDR 전달 | 종료 거래와 같은 ID의 CDR을 mock eMSP에 실제 전달 | 확인 |
| 고객용 모의 청구 | CDR·계약·요율을 연결해 명세 생성, CDR 해시 대조 | 확인 |
| 동일 CDR 중복 청구 방지 | 이전 직접 재전송 시험에서 청구서 수와 ID 유지 확인 | 별도 시험에서 확인; 매 재실행에는 미포함 |
| 사용자 직접 재검증 | 독립 실행, 로그·종료 코드·JSON·HTML 결과 자동 저장 | 실행 성공 확인 |
| 다른 팀원 PC의 신규 구성 | 보존된 로컬 이미지·컨테이너·DB에 의존 | 미완료 |

이 환경은 이후 계량 보고값의 과소·과대 변조와 신뢰 경계별 검증 동작을 비교하기 위한 정상 기준 환경입니다. **현재 정상 세션의 성공만으로 변조 취약성이나 실제 계량값의 진위를 입증하지는 않습니다.**

## 2. 실제 구현 구조와 역할

```text
Virtual EV ↔ EVerest 충전기 시뮬레이션
           ISO 15118-2 / PnC
                    │
                    │ OCPP 2.0.1: 인증·충전 거래·계량 보고
                    ▼
          CitrineOS OCPP Server
                    │ 거래 기록 → 세션/CDR 생성
                    ▼
          CitrineOS OCPI Server
                    │ OCPI 2.2.1: CDR 전달
                    ▼
             공식 mock eMSP
                    │ 내부 실험 API에서 수신 CDR 상태 조회
                    ▼
          추가 구현 Mock Retail Billing
                    │ 계약 확인·요금 계산·중복 검사
                    ▼
       모의 청구 명세 + SQLite 원장 + 감사 이벤트
```

| 구성요소 | 무엇을 하는가 |
|---|---|
| Virtual EV | 가상 차량. 충전기와 ISO 15118 통신을 수행 |
| EVerest manager | 충전기 소프트웨어와 시뮬레이션 모듈 실행. 계약 인증·충전·OCPP 보고 수행 |
| MQTT / Node-RED | 시뮬레이션 제어 메시지 전달 / 제어 UI 제공 |
| CitrineOS OCPP | 충전기 연결과 인증·거래·계량 이벤트 처리 |
| PostgreSQL / RabbitMQ / Hasura | 거래 등 데이터 저장 / 내부 메시지 전달 / 조회 API 제공 |
| CitrineOS OCPI | 충전 거래를 로밍 세션·CDR로 연결하고 eMSP에 전달 |
| 공식 mock eMSP | eMSP 역할의 실험용 수신기. CDR 요청·응답·검증 finding 관측 |
| Mock Retail Billing | 우리가 추가한 청구 계산 모듈. 실제 결제 기능 없음 |

**통신 경계:** OCPI 구간은 `CitrineOS OCPI → mock eMSP`입니다. `mock eMSP → Billing`은 내부 실험 API를 조회하는 연결이며 별도 OCPI 구간이 아닙니다.

## 3. 핵심 환경설정

| 항목 | 현재 값·구성 |
|---|---|
| 실행 기반 | Windows + Ubuntu WSL2 + Docker Desktop |
| 백엔드 Compose 프로젝트 | `coop-sil-billing` |
| 현재 EVerest Compose 프로젝트 | `coop-everest-local` |
| 보존한 이전 EVerest 프로젝트 | `coop-everest-citrine` — 중지 상태여도 정상 |
| 백엔드 / EVerest 네트워크 | `coop-sil-billing-net` / `coop-everest-local-net` |
| EVerest IPv6 | 활성화, `2001:db8:9::/64` |
| EVerest 실행 이미지 | `ev-pnc/manager:coop-local-20261116` — 보존된 실행 환경에서 만든 로컬 이미지 |
| EVerest 기반 태그 | `2025.10.0-single-phase` 계열 |
| CitrineOS 고정 소스 | `4fd7599b91c2fb6e6065e7c9b94be69880cced27` — 프로젝트 v2.1.0 병합 커밋 |
| 통신 프로토콜 | OCPP **2.0.1**, OCPI **2.2.1**, PnC **ISO 15118-2** |
| 충전기 ID / DB station 숫자 ID | `cp001` / `1` — 서로 다른 식별자 |
| 충전기 → CSMS 주소 | `ws://citrine:8081/cp001` — 컨테이너 내부 주소 |
| PnC 계약 eMAID | `NL123C10028948M` |
| 계약 체인 검증 | `verify_contract_cert_chain: true` |
| 테스트 OCSP responder | `http://manager:8888/` |
| 세션 로그 | 일반 로그·XML 로그 활성화, `/evidence/session-logs` |
| 모의 소매 요율 | 이번 USD 경로에서 `0.30 USD/kWh` |
| 저장 | DB·브로커·Billing은 named volume 사용. 증거는 작업 폴더에 저장 |

CitrineOS **제품 버전 2.1.0**과 **OCPP 2.0.1**은 서로 다른 숫자입니다. ISO 15118 차량↔충전기 TLS 세션과 OCPP 구간의 전송 보안도 구분합니다. 현재 OCPP 연결은 실험용 `ws://`이며 생산용 보안 구성이 아닙니다.

주요 호스트 접근 포트는 `127.0.0.1`에 바인딩합니다.

| 용도 | 호스트 포트 |
|---|---|
| CitrineOS API / OCPP | `18080` / `18081`, `18082` |
| OCPI / mock eMSP | `18085` / `18083` |
| Mock Billing / Hasura | `18088` / `18090` |
| MQTT / Node-RED | `12727` / `11880` |

## 4. 실제 성공한 한 거래의 연결 예시

2026-11-16 한국시간 **10:08:34 ~ 10:09:20**에 종료한 세션입니다. 새로 실행하면 ID와 수치는 달라집니다.

| 확인 대상 | 실제 값 |
|---|---|
| OCPP transactionId / OCPI session_id / CDR id | `8d135f23-a489-4e22-9f4a-e8e36d7d1bfc` |
| 계약 인증 | eMAID 요청, 같은 correlationId 응답에서 토큰·인증서 모두 `Accepted` |
| 거래 이벤트 | Started → Updated → Ended |
| 거래 종료 / 충전량 | `isActive=false` / `0.108 kWh` |
| DB·CDR·청구서 에너지 | 동일한 `0.108 kWh` |
| 고객용 모의 청구 | `0.108 × 0.30 = 0.03240 → 0.03 USD` |
| 청구서 ID | `SIM-160d80f986fa29efe920` |
| 청구 상태 | `SIMULATED_INVOICE_NOT_PAID`, `payment_attempted=false` |
| 최종 실행 결과 | `EXIT_CODE=0`, `review-summary.json`의 `passed=true` |

CDR의 **CPO total_cost**는 시간·기본료 등이 포함된 상류 요금일 수 있습니다. 위의 **고객용 소매 모의 청구액**과 다른 가격 모델이므로 두 금액이 같아야 하는 것은 아닙니다.

근거: [이 세션의 검토 요약](../diagnostics/local-review-20261116T010824Z/review-summary.json), [거래·CDR·청구 연결](../diagnostics/local-review-20261116T010824Z/delivery.json), [읽기 쉬운 결과](../diagnostics/local-review-20261116T010824Z/result.html).

## 5. 최종 수동 검증 시 직접 확인할 것

실행 명령과 정상 출력은 [직접 실행 안내](DIRECT_REVIEW.md)를 따릅니다. 자동 검사 통과 여부와 함께 **새로 실행한 동일 거래의 원본 항목**을 아래 순서로 확인합니다.

| 순서 | 직접 볼 증거 | 정상 기준 |
|---|---|---|
| 1 | 이번 작업의 `status.txt`, 실행 로그 | `EXIT_CODE=0`, 최종 PnC·데이터 연결 통과 로그 |
| 2 | `manager.log` | OCPP 2.0.1 연결·BootNotification 수락. manager를 재시작하지 않았다면 연결 로그 시각은 이번 충전보다 앞설 수 있음 |
| 3 | `<거래 ID>-eventlog.csv` | 해당 거래의 PaymentDetails·Authorization·PnC 인증·충전 종료 흐름 |
| 4 | `review-summary.json`의 `authorize` | eMAID와 인증서 hash 데이터가 있는 요청, 같은 correlationId의 토큰·인증서 `Accepted` 응답 |
| 5 | 같은 파일의 `transactions`, `events` | 해당 transactionId의 Started/Updated/Ended, 종료 시각 존재, 양수 에너지 |
| 6 | `delivery.json`의 이번 거래 correlation | `validated_ocpi_push`, `completed_csms_transaction`, `matching_snapshot_invoice`, `data_chain_observed` 모두 `true` |
| 7 | `review-summary.json`의 `invoice`, `checks` | CDR ID 연결, 에너지 일치, 계산 일치, 미결제 상태, 모든 checks `true` |

추가 원문이 필요하면 실행 로그의 `Exports:`에 표시된 `evidence/<UTC 시각>/`에서 `cdrs.json`, `cdr-wire.json`, `invoices.json`을 봅니다. CDR과 invoice의 해시 연결도 함께 확인합니다.

**주의:** `verify_backend.py`의 `PnC authentication: NOT VERIFIED`만으로 실패나 성공을 판단하지 않습니다. 이 검사는 API·DB·wire 상관관계만 판정합니다. 별도 `review-summary.json`의 인증 응답과 세션 로그를 함께 봅니다. 과거 성공 폴더가 아니라 **본인이 방금 실행한 폴더**인지 먼저 확인하세요.

## 6. 완료 범위와 남은 제한

- **이 PC의 정상 기준 경로는 검증됨:** 실제 소프트웨어 PnC 세션 → OCPP 거래 → OCPI CDR → 모의 청구.
- **팀 배포 재현은 미완료:** 다른 PC의 깨끗한 설치에서 G1~G5를 재현한 증거는 없음. 로컬 이미지·기존 DB·컨테이너에 의존.
- **연구 확장 실험은 별도:** 과소·과대 보고, 변경된 동일 ID CDR, 잘못된 계약/세션 등의 최종 종단 실험은 이번 정상 경로 검증에 포함하지 않음. 합성 Billing 테스트를 종단 실험으로 간주하지 않음.
- **인증서 상태 관리 제한:** SECC OCSP 상태 갱신 `GenericError` 경고가 남음. 이번 계약 인증 수락과 전체 PKI 관리 정상 여부는 구분.
- **수신 이력 내구성 제한:** mock eMSP는 재시작 시 메모리 CDR·wire 이력을 잃음. DB·청구서 보존과 다름.
- **범위 밖:** 생산 PKI, 물리 계측 기준값·계량 서명, 전체 OCPI 적합성, 실제 결제·Stripe·금융 정산.
- **작업 안정성:** Windows 페이지 파일 설정 수정 후 실행 여유 회복 확인. 독립 실행은 VS Code 종료를 견디지만 WSL 종료·Windows 재부팅은 견디지 못함.

## 7. 설정·설명·증거를 찾는 위치

| 파일 | 역할 |
|---|---|
| [DIRECT_REVIEW.md](DIRECT_REVIEW.md) | 사용자가 직접 실행할 명령과 정상 출력 |
| [everest.local.yml](../deploy/everest.local.yml) | 홈 경로에 의존하지 않는 현재 EVerest 구성 |
| [citrine.override.yml](../deploy/citrine.override.yml) | 백엔드 서비스·포트·저장 설정 |
| [PnC 설정](../config/config-sil-ocpp201-pnc-strict.yaml) | 계약 체인 검증·차량 TLS·세션 로그 |
| [OCPP 서버 설정](../config/websocket-servers.ocpp201.json) | OCPP 2.0.1 협상 설정 |
| [소매 요율 정책](../config/retail_policy.json) | 계약·고객 계정·통화별 실험 요율 |
| [review_local.sh](../scripts/review_local.sh) / [review_result.py](../scripts/review_result.py) | 재실행 흐름 / 별도 PnC 및 결과 대조 |
| [연구 완료 조건](RESEARCH_AND_ACCEPTANCE.md) | 정상 환경 구축 이후 연구·팀 재현의 완료 기준 |

`UPSTREAM.lock.json`과 일부 초기 문서의 상태 설명은 후속 로컬 검증 이전 시점에 작성되어 있습니다. 소스 고정 정보는 참고하되, 현재 완료 여부는 날짜가 있는 실제 실행 증거와 이 문서의 범위를 함께 확인합니다.
