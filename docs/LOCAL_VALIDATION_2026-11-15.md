# 로컬 SIL 종단 간 검증 — 2026-11-15

## 판정

이 PC의 접근 가능한 로컬 환경에서 다음 경로를 실제로 기동하고 한 번의 동일한 PnC 거래로 연결했다.

```text
Virtual EV → EVerest → CitrineOS OCPP 2.0.1 → CitrineOS OCPI 2.2.1
           → official mock eMSP → Mock Retail Billing
```

합성 CDR, RFID 또는 Remote Start를 완료 근거로 사용하지 않았다. 실제 ISO 15118-2 계약 인증서 세션의 OCPP `TransactionEvent`와 종료 CDR을 대조했다. 실제 결제·Stripe는 실행하지 않았다.

## 확인한 환경

- Windows 작업 복사본: `C:\Users\pet_who\.codex\.chatgpt-projects\g-p-6ab130675a0c81919d6c1ea30ba26977\work\coop-sil-billing-starter\coop-sil-billing`
- 원본 ZIP: `C:\Users\pet_who\Downloads\coop-sil-billing-starter.zip` (수정하지 않음)
- 기존 EVerest: `/home/hyebin/research/ev-pnc/everest-demo`
  - branch `main`, commit `686e370d6ed6460211b06e34a4cdf9438a22e81e`
  - 기존 변경 `M maeve/maeve-csms-ignore-ocsp.patch` 보존
  - 과거 기록의 계약 ID `UKSWI1234567915`와 실행 흔적은 확인했지만 기존 설정이 `verify_contract_cert_chain: false`였으므로 엄격한 PnC 성공 증거로 재사용하지 않았다.
- 기존 Maeve: `/home/hyebin/research/ev-pnc/vendor/maeve-csms`
  - detached commit `64a592fcf2ea43f961efa63e512908c7f6b8e496`
  - 기존 untracked `manager/services/ocsp_policy_matrix_test.go` 보존
- CitrineOS Core: `vendor/citrineos-core`, commit `4fd7599b91c2fb6e6065e7c9b94be69880cced27`
  - 수정은 seed의 mock 주소를 `host.docker.internal`에서 Compose DNS `mock-msp`로 바꾼 한 파일뿐이다.
- EVerest manager image: `ev-pnc/manager:2025.10.0-recovered`, image ID `sha256:520a2f93a5b09c9e86e777bfb1bcd276c699c6e1555ec5b7318343cd44276801`
- mock eMSP runtime: Node.js v24.16.0, pnpm 10.19.0
- Docker Desktop 4.56.0, Engine client/server 29.1.3, Compose v5.0.0-desktop.1
- WSL2: Ubuntu(기본), Ubuntu-24.04, docker-desktop
- `EV 충전 과금 실증 구조.md/.html` 및 팀장 메모는 `/home/hyebin` 아래 검색했으나 발견하지 못했다.

패키지 자체는 Git 저장소가 아니다. 따라서 push하지 않았고, 대상 공개 저장소도 임의로 정하지 않았다.

## 격리 구성

- 백엔드 Compose project: `coop-sil-billing`
- 백엔드 network: `coop-sil-billing-net`
- 백엔드 volumes: `coop-sil-billing_coop-db`, `coop-sil-billing_coop-mq`, `coop-sil-billing_coop-billing`
- EVerest Compose project: `coop-everest-citrine`
- EVerest network: `coop-everest-citrine-net` (`2001:db8:8::/64`)
- OCPP WebSocket: `ws://citrine:8081/cp001`
- charger ID / connection name: `cp001`
- 계약 eMAID: `NL123C10028948M`
- 호스트 포트: Citrine 18080/18081/18082, OCPI 18085, mock eMSP 18083, Billing 18088, Hasura 18090, EVerest MQTT 12727, Node-RED 11880

기존 EVerest 컨테이너·네트워크·볼륨과 기존 DB는 삭제하거나 초기화하지 않았다. 새 DB에서만 official migration/seed와 실험 계약 row를 실행했다.

## 변경 사항

- `deploy/citrine.override.yml`: 격리 네트워크·볼륨·포트, OCPP 2.0.1 서버 설정 mount, 서비스 healthcheck와 Billing 연결
- `config/websocket-servers.ocpp201.json`: CitrineOS가 OCPP 2.1이 아닌 2.0.1만 협상하도록 설정
- `config/retail_policy.json`: `NL123C10028948M` 계약과 `LAB-USD-030` 0.30 USD/kWh 소매 요율 등록
- `scripts/stack.sh`: 실험 eMAID seed, 서비스 준비 검사, 이미지 식별자 기록
- `config/config-sil-ocpp201-pnc-strict.yaml`: `verify_contract_cert_chain: true`, 세션 XML/log 활성화
- `deploy/everest.citrine.override.yml`: 기존 EVerest와 분리된 manager/MQTT/Node-RED 구성
- `scripts/everest_citrine.sh`: 테스트 PKI 생성·복원, 로컬 OCSP responder, EVerest/Virtual EV 세션 제어
- `scripts/verify_backend.py`: station DB 숫자 ID와 `cp001` 연결 이름을 혼동하던 비교를 고쳐 실제 CSMS transaction/CDR/Billing 상관관계를 판정

수정 전 원본은 `backups/20261115T224000/` 및 `backups/20261115T140000/`에 보관했다. 개인키 archive는 `.gitignore` 대상인 `diagnostics/private-pki/`에 mode 0600으로 두었고, 문서나 Git 대상 파일에 비밀값을 넣지 않았다.

## 실제 거래와 연결 증거

최종 거래의 단일 상관 키는 다음과 같다.

| 단계 | 값 |
|---|---|
| OCPP transactionId | `97258ded-e042-4bda-8ee8-bcedb7e8a999` |
| OCPI session_id | `97258ded-e042-4bda-8ee8-bcedb7e8a999` |
| OCPI CDR ID | `97258ded-e042-4bda-8ee8-bcedb7e8a999` |
| Billing invoice ID | `SIM-4b38b869de387183d559` |
| CDR SHA-256 | `4ef75b845f24c59681759a6e86848dbeaeabccfa9482d8774d847a74d44467f9` |

세션은 2026-11-15 13:49:01.929Z에 시작하여 13:49:34.700Z에 종료됐다. EVerest event log에는 SLAC match, ISO 15118 `PaymentDetailsReq/Res`, `AuthorizationReq/Res`, `PnC Authorization received`, 실제 charging loop, `Transaction Finished: EVDisconnected (0.068 kWh)`가 연속 기록돼 있다.

계약 인증서 공개 메타데이터:

- subject CN/eMAID `NL123C10028948M`
- leaf SHA-256 `05:9E:E2:41:AE:9C:ED:8C:66:AE:2A:D7:89:A7:D9:94:EF:75:9C:03:BD:08:95:35:D3:C6:BB:BF:5C:C8:30:2B`
- validity 2026-11-15T13:45:01Z–2028-11-14T13:45:01Z
- EVerest strict chain validation 성공, CitrineOS의 idToken와 certificate status `Accepted`
- OCSP 검증을 끄지 않고 격리 manager의 테스트 responder로 정상 응답시켰다.

재시작 후에도 EVerest는 `ocpp2.0.1`로 연결하고 BootNotification `Accepted`를 다시 받았다.

## 에너지와 청구 대조

- 종료 계량 에너지: 68 Wh = 0.068 kWh
- CDR `total_energy`: 0.068 kWh
- CDR 통화: USD
- 실험 eMSP 소매 요율: 0.30 USD/kWh (`LAB-USD-030`)
- 계산: 0.068 × 0.30 = 0.02040 USD
- `ROUND_HALF_UP` 최종 청구: 0.02 USD (`amount_minor: 2`)
- 상태: `SIMULATED_INVOICE_NOT_PAID`, `payment_attempted: false`

상류 CPO CDR에는 energy/time/flat 복합 tariff를 적용한 `total_cost` 1.54 USD(excl. VAT), 1.67 USD(incl. VAT)도 있다. 이는 이 실험의 eMSP 고객용 energy-only 소매 정책과 다른 가격 모델이다. 둘을 같은 금액으로 가장하지 않았다.

동일 CDR을 OCPI endpoint에 다시 POST한 뒤 Billing sync를 재실행했다. 응답은 OCPI status 1000이었고 invoice count는 1, invoice ID는 동일했으며 감사 이벤트는 `DUPLICATE`였다.

## 재시작 검증

`ocpp-db`, RabbitMQ, CitrineOS, Hasura, OCPI, Billing을 순차 재시작한 뒤 모두 healthy가 됐다. 거래·CDR hash·청구서 상관관계와 invoice 1건이 유지됐다. EVerest manager 컨테이너도 재시작하고 local OCSP/manager를 다시 올린 뒤 OCPP 2.0.1 Boot 수락을 확인했다.

official mock eMSP는 수신 CDR/wire trace를 메모리에만 보관한다. 이 때문에 원본 수신 이력을 잃지 않도록 mock eMSP 자체는 이 재시작 시험에서 제외했다. Billing의 named volume에는 CDR snapshot/hash와 청구서가 유지된다. mock eMSP까지 포함한 완전한 재시작 내구성은 **미완료**다.

## 증거 위치

- `diagnostics/end-to-end-delivery.json`: CSMS transaction→validated OCPI push→invoice hash 상관관계
- `diagnostics/duplicate-receipt-verification.json`: 중복 재수신 뒤 동일 invoice 상관관계
- `diagnostics/post-restart-verification.json`: 백엔드 재시작 뒤 동일 상관관계
- `diagnostics/everest-session/session-logs/2026-11-15T134855.593Z-97258ded-e042-4bda-8ee8-bcedb7e8a999/eventlog.csv`: 실제 ISO 15118/PnC 세션과 0.068 kWh
- `diagnostics/everest-session/pki-public-evidence.txt`: 공개 인증서 subject/issuer/기간/fingerprint
- `diagnostics/everest-session/csms-pnc-authorize-evidence.txt`: 동일 correlation의 eMAID/ISO 15118 인증서 hash 요청과 CSMS `Accepted` 응답
- `diagnostics/everest-session/ocsp-responder.log`: 테스트 OCSP 요청
- `diagnostics/everest-session/manager.log`: 재시작 후 OCPP 2.0.1/Boot 수락
- `evidence/20261115T135316Z/`: CDR, wire trace, invoice, billing event의 최초 scrubbed export
- `evidence/20261115T140130Z/`: 재시작·재검증 뒤의 scrubbed export
- `diagnostics/image-identities.jsonl`: 실제 실행 이미지 ID/digest
- `diagnostics/local-audit.json`: 기존 로컬 환경 읽기 전용 진단

`evidence/`와 `diagnostics/private-pki/`는 Git 제외 대상이다. 증거를 외부 공유하기 전에 식별자를 다시 검토해야 한다.

## 남은 제한

1. 생산 인증기관 인증서가 아니라 격리 실험용 PKI/OCSP이다.
2. mock eMSP의 CDR/wire 저장소는 메모리 기반이라 컨테이너 재시작 시 소실된다.
3. 계량값의 cryptographic signature verification은 `NOT_IMPLEMENTED`다.
4. 실제 결제, Stripe, 금융 정산, 세금·시간·주차 복합 소매 요금은 범위 밖이다.
5. 전체 OCPI 적합성 시험과 물리 계측기 기준값 대조는 수행하지 않았다.
6. `verify_backend.py`는 인증서 로그를 자동 판정하지 않으므로 JSON의 PnC flag는 false이며, PnC 판정은 별도 로그 묶음으로 수행했다.

## 재현 명령

Ubuntu WSL에서 실행한다. `seed`는 새 격리 DB를 처음 만들 때 한 번만 실행한다.

```bash
cd /mnt/c/Users/pet_who/.codex/.chatgpt-projects/g-p-6ab130675a0c81919d6c1ea30ba26977/work/coop-sil-billing-starter/coop-sil-billing

python3 scripts/init_env.py
python3 scripts/prepare_upstream.py
bash scripts/stack.sh config
bash scripts/stack.sh up
bash scripts/stack.sh seed

bash scripts/everest_citrine.sh up
bash scripts/everest_citrine.sh generate-pki
bash scripts/everest_citrine.sh configure
bash scripts/everest_citrine.sh start
bash scripts/everest_citrine.sh start-session
# 충전 계량 구간을 기다린 뒤
bash scripts/everest_citrine.sh stop-session

python3 scripts/verify_backend.py --require delivery --sync --since <UTC_START>
python3 scripts/collect_evidence.py --include-wire
```

일상 재실행에서는 `generate-pki`, `configure`, `seed`를 반복하지 않아도 된다. 중지는 named volume을 보존한다.

```bash
bash scripts/everest_citrine.sh down
bash scripts/stack.sh down
```

볼륨 삭제, Docker prune, 기존 DB 초기화 명령은 의도적으로 제공하지 않는다.
