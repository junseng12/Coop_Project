# 파일 구성도 — 무엇을 실행하고, 어디를 확인하는가

기준일: 2026-11-16. 현재 로컬 재검증 경로를 중심으로 정리했습니다.

**읽는 순서:** [환경 이해](ENVIRONMENT_SUMMARY_AND_MANUAL_REVIEW.md) → [직접 실행](DIRECT_REVIEW.md) → 이번 실행의 `result.html`과 원본 증거.

## 1. 전체 폴더 구성

괄호 안 한글은 이해를 돕는 역할 이름입니다. 실제 파일·폴더명은 왼쪽 영문 이름입니다.

```text
coop-sil-billing/                         ← 실험 작업 폴더
│
├─ docs/                                 ← 사람이 읽는 설명서
│  ├─ ENVIRONMENT_SUMMARY_AND_MANUAL_REVIEW.md  환경 목표·실제 구현·수동 검증 기준
│  ├─ DIRECT_REVIEW.md                    직접 실행 명령·정상 출력
│  └─ FILE_MAP.md                         현재 파일 구성도
│
├─ scripts/                              ← 실행·제어·검증 도구
│  ├─ detached.sh                        VS Code와 분리해 작업 실행
│  ├─ review_local.sh                    전체 재검증 순서 진행
│  ├─ stack.sh                           백엔드 환경 제어
│  ├─ everest_citrine.sh                 가상 충전 환경 제어
│  ├─ verify_backend.py                  거래·CDR·청구 연결 검사
│  ├─ review_result.py                   PnC 등 별도 증거 검사·보고서 생성
│  ├─ collect_evidence.py                수신 기록·청구 원문 수집
│  └─ check_host_memory.py               Windows 메모리 여유 확인
│
├─ deploy/                               ← 어떤 컨테이너를 어떻게 연결할지
│  ├─ everest.local.yml                  현재 EVerest 환경 구성
│  ├─ citrine.override.yml               공식 백엔드에 덧붙이는 실험 설정
│  └─ Dockerfile.billing                모의 청구 서비스 이미지 제작법
│
├─ config/                               ← 각 서비스가 사용할 규칙·설정값
│  ├─ config-sil-ocpp201-pnc-strict.yaml  PnC·충전 시뮬레이션·로그 설정
│  ├─ websocket-servers.ocpp201.json      OCPP 2.0.1 서버 설정
│  └─ retail_policy.json                 고객 계약·소매 요율 정책
│
├─ billing/                              ← 우리가 추가한 모의 청구 프로그램
│  ├─ app.py                             HTTP API·CDR 조회/동기화
│  ├─ engine.py                          계약 검사·계산·중복 처리·원장
│  └─ demo.py                            합성 CDR 청구 예제
│
├─ vendor/citrineos-core/                ← 고정 커밋의 공식 CitrineOS 소스
├─ tests/                                ← Python 자동 테스트
├─ fixtures/                             ← 테스트용 합성 입력
│
├─ diagnostics/                          ← 실행 상태·검사 결과·충전 로그
├─ evidence/                             ← API로 수집한 CDR·청구 원문 증거
├─ backups/                              ← 변경 전 파일 보관
│
├─ .env                                  ← 로컬 API 비밀값
├─ UPSTREAM.lock.json                    ← 공식 소스 커밋·목표 프로토콜 기록
└─ README.md                             ← 초기 프로젝트 개요
```

## 2. 가장 중요한 파일 8개

처음에는 아래 파일만 구분하면 됩니다.

| 직관적인 역할 이름 | 실제 파일 | 언제 보는가 |
|---|---|---|
| **환경 설명서** | [ENVIRONMENT_SUMMARY_AND_MANUAL_REVIEW.md](ENVIRONMENT_SUMMARY_AND_MANUAL_REVIEW.md) | 우리가 구성한 범위를 이해할 때 |
| **실행 설명서** | [DIRECT_REVIEW.md](DIRECT_REVIEW.md) | 직접 실행·수동 검증할 때 |
| **백그라운드 실행기** | [detached.sh](../scripts/detached.sh) | VS Code 창과 분리해서 시작할 때 |
| **전체 검증 진행자** | [review_local.sh](../scripts/review_local.sh) | 전체 실행 순서를 확인할 때 |
| **가상 충전기 조작 도구** | [everest_citrine.sh](../scripts/everest_citrine.sh) | 충전 환경 기동·세션 시작·종료 명령 확인 |
| **데이터 연결 검사기** | [verify_backend.py](../scripts/verify_backend.py) | 종료 거래·CDR 전달·청구 해시 연결 판정 확인 |
| **PnC·최종 결과 검사기** | [review_result.py](../scripts/review_result.py) | 인증 응답·세션·계량·청구 계산 판정 확인 |
| **모의 청구 계산기** | [engine.py](../billing/engine.py) | 실제 요금 계산·계약·중복 처리 로직 확인 |

`everest_citrine.sh`라는 파일명은 유지하지만 현재 제어 대상은 **`coop-everest-local`** 프로젝트입니다. 파일명과 컨테이너 프로젝트 이름이 다른 점에 유의하세요.

## 3. 실행 명령과 파일이 연결되는 흐름

사용자가 실행하는 명령은 다음입니다.

```bash
bash scripts/detached.sh bash scripts/review_local.sh
```

내부에서는 다음 파일들이 순서대로 역할을 맡습니다.

```text
detached.sh                         독립 작업 생성·출력 로그 저장
└─ review_local.sh                  전체 재검증 순서 실행
   ├─ check_host_memory.py          시작 가능한 메모리 여유 확인
   ├─ stack.sh config              백엔드 설정 검사
   ├─ docker start                 보존된 백엔드 컨테이너 기동
   ├─ verify_backend.py            서비스 준비 상태 확인
   ├─ everest_citrine.sh            로컬 EVerest 구성·기동·충전·종료
   ├─ verify_backend.py --sync      새 거래/CDR 연결·모의 청구 동기화 검사
   ├─ collect_evidence.py           API 원문 증거 저장
   └─ review_result.py              별도 PnC 증거·에너지·계산 검사
      ├─ review-summary.json       최종 판정과 세부 근거
      └─ result.html               사람이 읽는 보고서
```

`review_local.sh`는 서비스를 준비하고 검사를 호출하는 **진행자**입니다. 충전 동작 자체는 EVerest, 거래 처리는 CitrineOS, 청구 계산은 `billing/`이 수행합니다.

## 4. 결과는 어디에 생기는가

```text
diagnostics/
├─ jobs/
│  └─ coop-job-<UTC 시작 시각>-<번호>/   ← 작업이 잘 실행됐는지
│     ├─ command.txt                    실행한 명령
│     ├─ status.txt                     RUNNING 또는 EXIT_CODE=0 등
│     └─ output.log                     전체 실행 로그
│
├─ local-review-<UTC 시작 시각>/        ← 이번 충전이 검증됐는지
│  ├─ result.html                       사람이 읽는 최종 결과
│  ├─ review-summary.json               PnC·거래·계량·청구 판정과 근거
│  ├─ delivery.json                     거래/CDR/청구 연결 검사
│  ├─ services.json                     충전 전 서비스 접근 검사
│  ├─ manager.log                       보고서 생성 때 보관한 충전기 로그
│  ├─ <거래 ID>-eventlog.csv             해당 충전 세션의 상세 로그
│  └─ since.txt                         새 전달 판별용 기준 시각
│
├─ everest-session/                     ← 현재 충전 환경의 공유 로그
│  ├─ manager.log                       manager 출력
│  ├─ ocsp-responder.log                테스트 OCSP 응답기 로그
│  └─ session-logs/                     거래별 원본 세션 로그
│
└─ private-pki/                         ← 실험 인증서·개인키 보관

evidence/
└─ <UTC 수집 시각>/                     ← API 원문을 따로 확인할 때
   ├─ cdrs.json                         mock eMSP에 저장된 CDR
   ├─ cdr-wire.json                     CDR HTTP 요청·응답·검증 기록
   ├─ invoices.json                     모의 청구 명세
   ├─ billing-events.json               청구 감사 이벤트
   ├─ findings.json                     mock 검증 finding
   ├─ mock-health.json                  mock 상태
   └─ manifest.json                     수집 범위·실패 목록
```

**세 폴더의 차이:** `jobs/`는 작업 실행 상태, `local-review-…/`는 이번 실험 판정, `evidence/`는 판정에 참고할 수신 데이터 원문입니다.

이번 작업 로그의 `Review output:`이 결과 폴더를, `Exports:`가 원문 증거 폴더를 알려줍니다. 둘은 생성 시각이 달라 폴더 이름도 다를 수 있습니다. 이전 성공 결과와 이번 실행을 섞어 보지 마세요.

## 5. 나머지 파일은 무엇인가

| 분류 | 파일 | 용도·주의 |
|---|---|---|
| 백엔드 제어 | `scripts/stack.sh` | config·ps·logs 등 제공. `seed`는 최초 DB 구성용 |
| 초기 준비 | `scripts/init_env.py`, `scripts/prepare_upstream.py` | 비밀값과 공식 소스 작업본 준비. 일상 재검증의 시작 명령이 아님 |
| Windows 복구 | `scripts/fix_windows_memory.ps1` | 페이지 파일 설정 조회·관리자 적용. 평소 충전 때 실행할 필요 없음 |
| 기존 환경 조사 | `scripts/audit_local.py`, `scripts/audit_from_wsl.sh` | 기존 EVerest 환경의 읽기 전용 진단 |
| 이전 진입점 | `Run-CoopLab.cmd`, `scripts/run_local.sh` | 초기 audit/backend/check 경로. 현재 재검증에는 `detached.sh`와 `review_local.sh` 사용 |
| 이전 EVerest 구성 | `deploy/everest.citrine.override.yml` | 이전 외부 EVerest Compose에 덧붙이던 파일. 현재 기본 재검증 경로에서 미사용 |
| Billing 단독 실험 | `compose.billing.yml` | Billing만 띄우는 별도 구성. 전체 스택과 호스트 포트 18088이 겹침 |
| 구성요소 검사 | `scripts/check_mock_billing.py`, `scripts/billing_client.py`, `billing/demo.py` | mock/Billing 연결·API·합성 입력 실험. PnC 종단 성공 증거와 구분 |
| 자동 테스트 | `tests/test_billing.py`, `tests/test_evidence.py`, `tests/test_sync.py` | 계산·상관관계·동기화 검사 |
| 합성 입력 | `fixtures/cdr_baseline.json` | 테스트용 CDR. 실제 충전에서 수집한 CDR과 구분 |
| 과거 기록 | `docs/LOCAL_VALIDATION_2026-11-15.md`, `docs/VERIFICATION.md` | 이전 실행 결과. 현재 수동 실행에는 새 결과 폴더 사용 |
| 초기 설계·연구 | `docs/SETUP.md`, `docs/LOCAL_RUN.md`, `docs/SOURCE_REVIEW.md`, `docs/RESEARCH_AND_ACCEPTANCE.md` | 초기 구성 절차·소스 검토·연구 완료 기준 |

## 6. 어떤 파일을 바꾸면 무엇이 달라지는가

| 바꾸려는 내용 | 관련 설정 | 의미 |
|---|---|---|
| 고객 계약·소매 요율 | [retail_policy.json](../config/retail_policy.json) | 누구에게 어떤 요율을 적용할지 |
| PnC·차량 통신·세션 로그 | [config-sil-ocpp201-pnc-strict.yaml](../config/config-sil-ocpp201-pnc-strict.yaml) | 충전 시뮬레이션과 인증 동작 |
| OCPP 프로토콜·서버 포트 | [websocket-servers.ocpp201.json](../config/websocket-servers.ocpp201.json) | 관리 서버가 어떤 연결을 받을지 |
| EVerest 이미지·네트워크·자원 | [everest.local.yml](../deploy/everest.local.yml) | 가상 충전 환경의 실행 구조 |
| 백엔드 포트·볼륨·서비스 설정 | [citrine.override.yml](../deploy/citrine.override.yml) | 관리·로밍·청구 서비스의 실행 구조 |

설정 파일 수정만으로 실행 중인 서비스에 항상 즉시 반영되지는 않습니다. 적용 방법은 서비스에 따라 다릅니다. **최종 정상 검증 중에는 기준 설정을 유지하고**, 변경 실험은 별도 실행과 증거로 구분하는 편이 좋습니다.

## 7. 파일과 컨테이너·이미지·볼륨의 차이

| 이름 | 쉽게 말하면 | 이 환경의 예 |
|---|---|---|
| 소스·설정 파일 | 실행 방법과 규칙을 적은 문서·코드 | `scripts/`, `config/`, `deploy/`, `billing/` |
| 이미지 | 프로그램과 실행 환경을 담은 틀 | `ev-pnc/manager:coop-local-20261116` |
| 컨테이너 | 이미지로 만든 실행 인스턴스 | `coop-everest-local-manager-1` |
| 볼륨 | 컨테이너와 별도로 보관하는 데이터 | DB·Billing 원장 저장소 |
| 호스트 로그 폴더 | 컨테이너에서 나온 기록을 PC 파일로 보관 | `diagnostics/everest-session/` |

**파일 구성도만으로 모든 실행 내용이 작업 폴더 안에 있다고 생각하면 안 됩니다.** 현재 EVerest의 프로그램·일부 설정은 Docker 로컬 이미지 안에 있고, DB·Billing 영속 데이터는 Docker 볼륨에 있습니다. 작업 폴더의 증거는 그 데이터의 조회·수집 결과입니다.

`.env`, `diagnostics/private-pki/`, 실험용 개인키를 포함한 로컬 이미지는 외부 공유 대상에서 제외합니다. 실제 파일명을 바꾸지는 않았으며, 이 문서의 한글 역할 이름으로 구분해서 보면 됩니다.
