# 코드 구성과 실험 상호작용

이 문서는 현재 공개 GHCR runtime과 `clean_everest.sh` 경로를 기준으로 합니다. 명령은 저장소 루트에서 실행합니다. [README](../README.md)의 정상 기준을 먼저 확보하세요.

## 코드의 출처

| 영역 | 위치 | 수행하는 일 |
|---|---|---|
| 이 저장소 | `scripts/`, `billing/`, `config/`, `deploy/` | 환경 제어·검사·실험용 청구 |
| 공식 CitrineOS 소스 | 설치 시 준비하는 `vendor/citrineos-core/` | OCPP·거래 DB·OCPI 변환·mock eMSP |
| 공식 EVerest runtime | GHCR 이미지 `/ext/dist` | Virtual EV·EVSE·ISO 15118·OCPP201 모듈 |
| 로컬 상태 | Docker `/state` 볼륨 | 생성된 개인키·테스트 인증서·OCPP DB·큐·오류 이력 |

EVerest 바이너리는 [공개 runtime 설명](PUBLIC_RUNTIME.md)의 고정 공식 이미지에서 가져옵니다. 이 저장소 안에 EVerest 전체 C++ 소스가 들어 있는 것은 아닙니다. 실제 compiled module 수정에는 별도 소스 작업과 이미지 빌드가 필요합니다.

## 실행 호출 관계

```text
bootstrap_public.sh
  ├─ init_env.py → .env 로컬 생성
  ├─ prepare_upstream.py → 고정 Core 소스 + mock DNS 패치
  ├─ stack.sh up / 새 DB에만 seed → 백엔드 준비
  └─ clean_everest.sh pull / up → 고정 GHCR runtime 실행

review_clean_runtime.sh
  ├─ verify_backend.py --require services
  ├─ clean_everest.sh up
  ├─ clean_everest.sh start-session
  ├─ 기본 45초 → stop-session
  ├─ verify_backend.py --require delivery --sync
  ├─ review_result.py --manager coop-everest-clean-manager-1
  └─ collect_evidence.py --include-wire
```

`detached.sh`는 이 호출을 `systemd-run --user`로 분리하고 작업 로그·종료 코드를 남깁니다. WSL 종료나 Windows 재부팅을 넘어서 실행되지는 않습니다.

## 역할별 파일

| 파일 | 읽을 내용 |
|---|---|
| [IMAGES.lock.json](../IMAGES.lock.json) | 배포 runtime의 registry digest |
| [UPSTREAM.lock.json](../UPSTREAM.lock.json) | Core 소스 커밋과 프로토콜 목표. 초기 상태 필드는 과거 기록임 |
| [everest.clean.yml](../deploy/everest.clean.yml) | `coop-everest-clean`, IPv6, 포트, `/state` 볼륨 |
| [runtime Dockerfile](../deploy/everest-runtime/Dockerfile) | 고정 공식 바이너리·새 OS·최종 이미지 구성 |
| [sanitize.py](../deploy/everest-runtime/sanitize.py) | 이미지에서 기존 키·DB·호스트 상태 제거 |
| [initialize.py](../deploy/everest-runtime/initialize.py) | 최초 PKI 생성, 암호와 상태 경로 연결 |
| [entrypoint.sh](../deploy/everest-runtime/entrypoint.sh) | 로컬 OCSP responder와 manager 수명 관리 |
| [strict YAML](../config/config-sil-ocpp201-pnc-strict.yaml) | 모듈 연결·계약 체인 검증·세션 로깅 |
| [citrine.override.yml](../deploy/citrine.override.yml) | 백엔드 서비스·포트·볼륨·OCPP 설정 mount |
| [verify_backend.py](../scripts/verify_backend.py) | 종료 거래·검증된 CDR push·청구 snapshot hash 대조 |
| [review_result.py](../scripts/review_result.py) | 이번 거래 전 인증 요청/응답·세션·에너지·계산 판정 |
| [billing/app.py](../billing/app.py) | 수신 CDR snapshot 조회·HTTP API |
| [billing/engine.py](../billing/engine.py) | 계약·필드 검사, 요율 snapshot, 계산·중복·충돌 처리 |

공식 OCPI → mock eMSP 구간과 `/_mock/state/cdrs` → Billing 내부 adapter를 구분합니다. `/api/sync`는 조회한 CDR로 청구 처리를 요청하는 API이며 자동 결제 webhook이 아닙니다. `/api/bill-cdr`는 수동/fixture 단위시험 경로입니다.

## 조작 위치를 해석하는 방법

- **YetiSimulator/powermeter:** `yeti_driver_1`의 계량 생성. EVerest upstream C++ 영역이며 YAML만 바꿔 임의 값 변조기가 생기지는 않습니다.
- **OCPP adapter/proxy:** 생성된 값과 서버 수신값 사이를 비교합니다. proxy는 별도 구현 대상이며 현재 배포에 준비돼 있다고 가정하지 않습니다.
- **CitrineOS transaction/meter:** 실제 서버가 저장·집계하는 계층입니다. vendor 소스 커밋과 패치를 남깁니다.
- **OCPI mapper/proxy:** 서버 거래와 CDR total_energy 사이의 변환·전송 계층입니다.
- **retail_policy/engine:** 수신한 CDR에 대한 고객용 소매 요율과 계산입니다. 상류 CPO total_cost와는 별도 가격 모델입니다.

한 계층씩 바꾸고, 변조 경로 밖의 SIL 기준 에너지를 별도로 기록해야 과소·과대 보고를 비교할 수 있습니다. 모든 단계의 값이 일치한다는 사실만으로 현실의 참값을 증명하지는 않습니다.

## 수동 세션의 검사와 증거 수집

백엔드와 clean runtime이 준비됐다는 전제입니다. 별도의 실험 실행이 동시에 진행되지 않아야 합니다.

```bash
RUN="diagnostics/manual-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN"
date -u +%Y-%m-%dT%H:%M:%SZ > "$RUN/since.txt"
bash scripts/clean_everest.sh start-session
```

원하는 시점에 실험 동작을 수행하고 종료합니다.

```bash
bash scripts/clean_everest.sh stop-session
sleep 12
cp diagnostics/clean-everest/manager.log "$RUN/manager.log"
python3 scripts/collect_evidence.py --include-wire
```

실험 결과가 실패하더라도 이미 수집한 증거를 보존합니다. 다음 검사는 정상 기준과의 비교용이며 예상한 불일치 때문에 실패할 수 있습니다.

```bash
python3 scripts/verify_backend.py --require delivery --sync --since "$(cat "$RUN/since.txt")" --out "$RUN/delivery.json"
```

`--sync`는 Billing 원장·감사 이벤트를 변경합니다. 과금 처리 전후를 비교하는 실험이라면 먼저 `collect_evidence.py`로 이전 상태를 수집하고 호출 시점을 기록하세요. 정상 전달 검사가 통과한 경우에만 다음의 정상 PnC 요약을 만듭니다.

```bash
python3 scripts/review_result.py "$RUN" --manager coop-everest-clean-manager-1 --runtime-config /state/everest.yaml
```

`review_result.py`는 성공한 delivery correlation을 전제로 하므로, 의도적으로 실패시킨 실험에 결과 HTML이 없다고 원문 증거까지 없는 것은 아닙니다. 에너지 불일치 등은 `delivery.json`, 원본 이벤트·CDR·invoice를 직접 대조합니다. 동기화 후 청구 상태도 보존하려면 원문 수집을 다시 실행하고 그 export 경로를 기록합니다.

### 원본 TransactionEvent와 meterValue 보존

정상 요약 JSON은 이벤트 일부 필드만 보관합니다. 전체 원본 이벤트가 필요하면 **대상 transactionId를 지정해** 읽기 전용 조회합니다. 아래는 성공한 정상 요약에서 ID를 가져오는 예입니다. 실패 실험은 DB·로그에서 식별한 ID를 명시하세요.

```bash
python3 - "$RUN" <<'PY'
import json, subprocess, sys
from pathlib import Path
from uuid import UUID
run = Path(sys.argv[1])
tid = str(UUID(json.loads((run / "review-summary.json").read_text())["results"][0]["transaction_id"]))
query = '''SELECT coalesce(json_agg(t),'[]'::json) FROM
(SELECT * FROM "TransactionEvents" WHERE "transactionInfo"->>'transactionId'=''' + "'" + tid + "' ORDER BY timestamp) t"
raw = subprocess.check_output(["docker", "exec", "coop-sil-billing-ocpp-db-1", "psql", "-U", "citrine", "-d", "citrine", "-At", "-c", query], text=True)
(run / "ocpp-transaction-events-full.json").write_text(json.dumps(json.loads(raw), indent=2))
PY
```

**필수 원문 보존 항목**에는 해당 이벤트의 `meterValue` 및 시간·단위·누적값이 포함됩니다. 버전·메시지에 따라 필드가 비어 있을 수도 있으므로 그 자체를 관측 결과로 남기세요. 로그·JSON에는 계약 식별자 등이 있으므로 원문을 그대로 공개 저장소에 올리지 않습니다.

## 판정과 한계

- `verify_backend.py`: 실제 CDR POST의 HTTP/OCPI 응답·schema finding·정규화 JSON hash·종료 거래·모의 invoice 연결을 확인합니다.
- `review_result.py`: 이번 거래 시작 전 15초 이내의 eMAID 요청, 같은 correlationId의 수락 응답, 해당 거래 세션 로그·에너지·계산을 확인합니다. 일반적인 인증 적합성 시험 전체가 아닙니다.
- `billing.engine.sha`: 키 정렬·공백 제거·UTF-8 JSON 직렬화 후 SHA-256입니다. HTTP rawBody의 바이트 해시가 아닙니다.
- `DUPLICATE`: 같은 CDR snapshot 재처리와 실제 OCPI 재전송은 다른 실험입니다. README의 별도 검사는 전자만 다룹니다.
- mock schema finding을 기록했다는 사실과 요청을 거부했다는 사실은 다릅니다. 현재 공식 mock에 대한 관측을 실제 상용 eMSP 전체로 일반화하지 않습니다.

현재 증거와 미검증 범위는 [PUBLIC_VALIDATION.json](PUBLIC_VALIDATION.json), 이미지 출처는 [PUBLIC_RUNTIME.md](PUBLIC_RUNTIME.md)를 확인하세요.
