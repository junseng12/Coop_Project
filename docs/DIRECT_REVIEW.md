# 직접 실행·검토 안내

작성 기준: 2026-11-16. 이 PC에서 성공한 실제 실행 로그와 현재 스크립트를 기준으로 정리했습니다.

## 먼저 알아둘 점

- Windows에서 Docker Desktop을 실행한 후 **Windows Terminal의 Ubuntu 또는 VS Code의 WSL 터미널**을 사용합니다.
- VS Code 관리자 권한은 필요하지 않습니다.
- 반드시 아래의 **실험 작업 폴더로 이동**해야 합니다. 다른 ChatGPT 프로젝트 폴더에서는 `scripts/detached.sh`를 찾을 수 없습니다.
- 코드 블록의 명령어만 복사합니다. 프롬프트(`pet_who@...$`)나 출력 예시는 복사하지 않습니다.
- 명령어 줄 끝에 `\`를 추가하지 않습니다.
- 이 안내는 이 PC에 보존된 이미지·컨테이너·DB를 사용하는 재실행 절차입니다. 새 PC에 처음 설치하는 절차는 아닙니다.

## 1. 작업 폴더로 이동

**명령어**

```bash
cd /mnt/c/Users/pet_who/.codex/.chatgpt-projects/g-p-6ab130675a0c81919d6c1ea30ba26977/work/coop-sil-billing-starter/coop-sil-billing
pwd
ls scripts/detached.sh scripts/review_local.sh
```

**정상 출력 예시**

```text
/mnt/c/Users/pet_who/.codex/.chatgpt-projects/g-p-6ab130675a0c81919d6c1ea30ba26977/work/coop-sil-billing-starter/coop-sil-billing
scripts/detached.sh  scripts/review_local.sh
```

파일 이름 두 개가 보이면 올바른 폴더입니다.

## 2. Docker와 메모리 확인

**명령어**

```bash
docker version
docker compose version
python3 scripts/check_host_memory.py
```

**정상 출력 예시 — 핵심 부분**

```text
Client:
 Version: 29.1.3
...
Server: Docker Desktop ...
 Engine:
  Version: 29.1.3
...
Docker Compose version v5.0.0-desktop.1
Windows commit: 70.0%, headroom: 10.94 GiB
```

버전과 숫자는 달라질 수 있습니다. `docker version`에 **Client와 Server가 모두 표시**되어야 합니다. 메모리 검사에 `BLOCKED`가 없어야 합니다.

현재 실행기는 Windows 메모리 커밋 사용률 **85% 미만**, 커밋 여유 **6GiB 이상**을 시작 기준으로 사용합니다. 이는 실험 시작을 위한 보수적인 기준이며, 물리 RAM 여유와는 다른 값입니다.

## 3. 자동 재검증 시작

**명령어**

```bash
bash scripts/detached.sh bash scripts/review_local.sh
```

**정상 출력 예시**

```text
Running as unit: coop-job-20261116T010824-3407.service; invocation ID: ...
Job: coop-job-20261116T010824-3407
Log: /.../diagnostics/jobs/coop-job-20261116T010824-3407/output.log
Status: /.../diagnostics/jobs/coop-job-20261116T010824-3407/status.txt
Survives VS Code closing; does not survive WSL shutdown or Windows restart.
```

`/.../`는 예시에서 생략한 작업 폴더 경로입니다. 실제 출력에는 전체 경로가 표시됩니다. 시간과 작업 번호는 실행마다 바뀝니다.

**이 출력은 작업을 접수했다는 뜻입니다. 아직 검증 완료는 아닙니다.**

실행기는 다음을 자동으로 수행합니다.

1. 메모리와 Compose 설정 검사
2. 기존 백엔드 기동 및 준비 상태 대기
3. 로컬 EVerest 기동
4. 새 PnC 모의 충전 세션 시작
5. 약 45초 후 충전 종료
6. 새 거래 → OCPI CDR → 모의 청구서 연결 검사
7. 별도 PnC 인증 응답·세션 로그·충전량·청구 계산 검사
8. 결과 JSON과 HTML 저장

서비스 준비 시간과 재시도에 따라 전체 실행 시간은 달라집니다. 완료 전에 같은 명령을 반복 실행하지 마세요.

## 4. 진행 로그 보기

**명령어**

```bash
LATEST_JOB="$(ls -1dt diagnostics/jobs/coop-job-* | head -1)"
echo "$LATEST_JOB"
cat "$LATEST_JOB/status.txt"
tail -f "$LATEST_JOB/output.log"
```

작업을 시작할 때 출력된 `Job` 이름과 `echo` 결과가 같은지 확인합니다. 여러 작업을 시작했다면 해당 작업의 경로를 직접 지정하세요.

**정상 진행 중 상태**

```text
RUNNING
```

**정상 로그 예시 — 주요 줄**

```text
Windows commit: 70.1%, headroom: 10.93 GiB
Review output: /.../diagnostics/local-review-20261116T010824Z
Compose syntax validation passed; no containers started.
EVerest/Citrine Compose syntax validation passed.
...
SERVICES_REACHABLE_NO_DATA_CHAIN | PnC authentication: NOT VERIFIED
...
DATA_CHAIN_OBSERVED | PnC authentication: NOT VERIFIED
...
Review: /.../diagnostics/local-review-20261116T010824Z/result.html
Data chain and separate PnC evidence checks passed.
Result: /.../diagnostics/local-review-20261116T010824Z/delivery.json
```

- `SERVICES_REACHABLE_NO_DATA_CHAIN`: 서비스는 접근 가능하지만 현재 수신 이력에 검증할 데이터 연결이 없는 상태입니다. 새 충전 전에는 정상적으로 나올 수 있습니다.
- `DATA_CHAIN_OBSERVED`: 종료 거래·검증된 CDR 전달·모의 청구서의 연결을 확인했다는 뜻입니다.
- `PnC authentication: NOT VERIFIED`: 이 줄을 출력하는 `verify_backend.py` 자체는 인증서 로그를 판정하지 않습니다. 이후 별도 검사 결과를 확인해야 합니다.
- **`Data chain and separate PnC evidence checks passed.`**: 연결 검사와 별도 PnC 증거 검사가 모두 통과한 최종 로그입니다.

`tail -f`는 작업 완료 후에도 화면을 계속 기다립니다. 마지막 줄이 보이면 **Ctrl+C**로 로그 보기만 종료합니다. 이때 독립 실행 작업은 중단되지 않습니다.

## 5. 최종 종료 상태 확인

로그 보기를 종료한 후 실행합니다.

```bash
cat "$LATEST_JOB/status.txt"
```

**정상 완료**

```text
EXIT_CODE=0
```

| 출력 | 의미 |
|---|---|
| `RUNNING` | 아직 진행 중. 중단된 작업은 이 상태가 남을 수도 있으므로 로그도 확인 |
| `EXIT_CODE=0` | 전체 실행 성공 |
| `EXIT_CODE=1` 등 0이 아닌 값 | 실패. 해당 작업의 `output.log` 확인 |

작업을 강제로 종료하거나 Windows/WSL이 종료되면 정상적인 종료 코드 기록을 남기지 못할 수 있습니다.

## 6. 이번 결과 확인

**명령어**

```bash
LATEST_REVIEW="$(ls -1dt diagnostics/local-review-* | head -1)"
echo "$LATEST_REVIEW/result.html"
python3 -m json.tool "$LATEST_REVIEW/review-summary.json"
```

실행 로그의 `Review output:` 경로와 `LATEST_REVIEW`가 같은 실행을 가리키는지 확인합니다. 실패한 실행 폴더에는 최종 보고서가 없을 수 있습니다.

**정상 JSON 예시 — 실제 성공 결과에서 발췌**

```json
{
  "passed": true,
  "results": [
    {
      "transaction_id": "8d135f23-a489-4e22-9f4a-e8e36d7d1bfc",
      "checks": {
        "runtime_strict_certificate_chain": true,
        "session_payment_details": true,
        "session_authorization": true,
        "session_finished": true,
        "csms_token_and_certificate_accepted": true,
        "transaction_completed_with_energy": true,
        "started_updated_ended": true,
        "db_cdr_invoice_energy_equal": true,
        "retail_calculation_correct": true,
        "no_payment": true
      },
      "invoice": {
        "energy_kwh": "0.108",
        "unrounded_amount": "0.03240",
        "amount_decimal": "0.03",
        "currency": "USD",
        "payment_attempted": false,
        "status": "SIMULATED_INVOICE_NOT_PAID"
      }
    }
  ]
}
```

실제 파일에는 거래·인증 요청/응답 등 추가 항목이 있습니다. 위 예시는 일부 항목을 생략한 것입니다.

**정상 판단 기준**

- 최상위 `passed`가 `true`
- 이번 거래의 `checks`가 모두 `true`
- 충전량이 0보다 크고 거래가 종료됨
- 모의 청구액이 충전량 × 0.30 USD/kWh를 최종 소수 둘째 자리에서 반올림한 금액과 같음
- `payment_attempted: false`, `SIMULATED_INVOICE_NOT_PAID`

거래 ID·충전량·금액은 매번 달라질 수 있습니다. 예를 들어 위 결과는 다음 계산입니다.

```text
0.108 kWh × 0.30 USD/kWh = 0.03240 USD → 0.03 USD
```

`no_payment: true`는 **실제 결제를 시도하지 않았다는 검사가 통과**했다는 뜻입니다. 납부 완료를 의미하지 않습니다.

### 결과 파일별 의미

| 파일 | 내용 |
|---|---|
| `result.html` | 브라우저로 읽는 이번 실행 결과 |
| `review-summary.json` | 별도 PnC·거래·에너지·모의 청구 검사 |
| `delivery.json` | 거래·CDR 전달·청구서 해시 연결 검사 |
| `services.json` | 충전 전 서비스 접근 검사 |
| `manager.log` | 이번 보고서 생성 시점에 보관한 EVerest 로그 |
| `<거래 ID>-eventlog.csv` | 해당 거래의 세션 로그 |
| `since.txt` | 새 CDR 전달을 판별하는 UTC 기준 시각 |

결과 폴더 이름과 로그 시각은 UTC 기준일 수 있습니다. 한국시간은 UTC에 9시간을 더합니다.

## 7. 컨테이너 상태 확인 — 선택 사항

```bash
bash scripts/stack.sh ps
bash scripts/everest_citrine.sh ps
```

**정상 출력 예시 — 이름과 상태만 요약**

```text
coop-sil-billing-ocpp-db-1          Up ... (healthy)
coop-sil-billing-amqp-broker-1      Up ... (healthy)
coop-sil-billing-graphql-engine-1   Up ... (healthy)
coop-sil-billing-citrine-1          Up ... (healthy)
coop-sil-billing-citrineos-ocpi-1    Up ... (healthy)
coop-sil-billing-mock-msp-1         Up ... (healthy)
coop-sil-billing-billing-1          Up ... (healthy)
coop-everest-local-manager-1       Up ...
coop-everest-local-mqtt-server-1   Up ...
coop-everest-local-nodered-1       Up ... (healthy)
```

실제 출력에는 IMAGE·COMMAND·PORTS 등의 열도 있습니다. 시작 직후에는 `health: starting`이 보일 수 있습니다. manager와 MQTT는 별도 healthcheck가 없어 `(healthy)` 없이 `Up`으로 표시됩니다.

새 EVerest 프로젝트 이름은 **`coop-everest-local`**입니다. 보존된 이전 `coop-everest-citrine` 컨테이너는 중지 상태여도 정상입니다.

## 8. 자주 나오는 오류

| 메시지 | 확인할 사항 |
|---|---|
| `scripts/detached.sh: No such file or directory` | 1단계 `cd`부터 다시 실행 |
| Docker API 연결 실패 | Docker Desktop 실행 및 WSL 연결 확인 |
| `permission denied ... docker.sock` | WSL 사용자 권한 문제. 이미 docker 그룹에 등록됐다면 `newgrp docker` 후 재확인. VS Code 관리자 실행과 별개 |
| `BLOCKED: enable Windows automatic pagefile management...` | 메모리 사용률·여유 확인. 자동 관리 설정과 재부팅 반영 확인 |
| `Another local review is already running.` | 기존 실행의 로그와 상태 확인. 중복 실행 중지 |
| `BLOCKED`가 서비스 기동 초기에 잠깐 출력됨 | 준비 중 재시도로 회복할 수 있음. 최종 로그와 종료 코드로 판단 |
| `Backend readiness timed out.` | 백엔드 준비 실패. 해당 작업의 로그와 `services.json` 확인 |
| `No new BootNotification response.` | EVerest 연결 확인 필요. `manager.log` 확인 |
| `Delivery verification failed...` | 해당 실행의 `delivery.json`과 `manager.log` 확인 |
| `review-summary.json`이 없음 | 아직 실행 중이거나 앞 단계 실패. 먼저 작업 상태와 로그 확인 |

## 구성과 검증 범위

- `/home/hyebin` 없이 `deploy/everest.local.yml`을 사용합니다.
- 로컬 이미지 `ev-pnc/manager:coop-local-20261116`는 이 PC의 보존된 실행 환경을 바탕으로 만들었습니다.
- 실행기는 DB 초기화, `seed`, PKI 재생성을 반복하지 않습니다. 테스트 인증서 복원은 자동 수행합니다.
- 기존 DB·청구서·원본 컨테이너를 보존합니다. 실행 후 서비스는 켜 둡니다.
- 독립 실행은 VS Code 창 종료를 견디지만 **WSL 종료·Windows 재부팅을 넘어서 계속 실행되지는 않습니다.**
- SECC 인증서 OCSP 상태 갱신 경고는 남아 있습니다. 계약 인증 성공과 인증서 상태 관리 전체의 정상 여부는 구분합니다.
- mock eMSP는 재시작하면 과거 메모리 수신 이력을 잃습니다. DB와 청구서는 유지되며 이번 실행에서 새 증거를 수집합니다.
- 생산 PKI·실제 결제·물리 계량 기준값·계량 서명·전체 OCPI 적합성을 검증한 것은 아닙니다.
- 로컬 runtime 이미지에는 실험용 개인키가 포함되므로 외부에 게시하지 않습니다.

## 가장 짧은 실행 순서

```bash
cd /mnt/c/Users/pet_who/.codex/.chatgpt-projects/g-p-6ab130675a0c81919d6c1ea30ba26977/work/coop-sil-billing-starter/coop-sil-billing
bash scripts/detached.sh bash scripts/review_local.sh
LATEST_JOB="$(ls -1dt diagnostics/jobs/coop-job-* | head -1)"
tail -f "$LATEST_JOB/output.log"
```

최종 통과 로그가 보이면 Ctrl+C를 누르고 다음을 실행합니다.

```bash
cat "$LATEST_JOB/status.txt"
LATEST_REVIEW="$(ls -1dt diagnostics/local-review-* | head -1)"
python3 -m json.tool "$LATEST_REVIEW/review-summary.json"
```

`EXIT_CODE=0`과 `"passed": true`를 확인하면 됩니다.
