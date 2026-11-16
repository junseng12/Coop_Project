# 구축·연동 절차

## 0. 기존 환경 보존

기존 EVerest 프로젝트에서 읽기 전용 `audit_local.py`를 먼저 실행합니다. 현재 성공하는 정상 세션 로그와 Git diff를 **로컬에** 보존합니다. 환경 확인 전 `git pull`, `git reset --hard`, `docker system prune`, `docker compose down -v`를 수행하지 않습니다.

공유 문서 `EV 충전 과금 실증 구조.md/html` 원문은 이 패키지를 만들 때 접근하지 못했습니다. 사용자 메시지에 붙여넣은 구성 요약과 공식 저장소를 비교한 결과만 반영했습니다.

기존 버전이 무조건 잘못된 것은 아닙니다. 작동하는 EVerest는 유지하고, 새 CSMS 쪽 소스 버전·연결 파라미터를 먼저 맞춥니다.

## 1. 독립 Billing 테스트

```bash
python3 -m unittest discover -s tests -v
python3 -m billing.demo --out evidence/billing-component-demo.json
```

이 단계는 합성 CDR로 구현 코드의 동작만 확인합니다. 정상·변조 EVerest 실행을 대신하지 않습니다.

## 2. 새로운 CitrineOS/OCPI/mock-msp/Billing 후보 스택

```bash
python3 scripts/init_env.py
python3 scripts/prepare_upstream.py
bash scripts/stack.sh config
bash scripts/stack.sh up
bash scripts/stack.sh seed
bash scripts/stack.sh ps
```

`prepare_upstream.py`는 **이 패키지 안의 vendor/citrineos-core만** 생성·수정합니다. 잠금 커밋과 다른 기존 checkout, 사용자 수정이 발견되면 보존하고 중지합니다. 공식 소스의 seed 파트너 주소만 내부 DNS로 변경하며, 변경 내역을 `diagnostics/vendor-patch.json`에 저장합니다. 공식 소스에 남아 있는 공개 개발용 계정/토큰은 실제 비밀이 아니지만 이 구성은 외부 공개에 적합하지 않습니다.

| 호스트에서 보는 주소 | 서비스 내부 주소 | 목적 |
|---|---|---|
| `http://127.0.0.1:18080/docs` | `http://citrine:8080` | OCPP 서버 API 문서 |
| `127.0.0.1:18081` | `citrine:8081` | OCPP WebSocket 후보 리스너 |
| `127.0.0.1:18082` | `citrine:8082` | 인증 리스너 후보 |
| `http://127.0.0.1:18085/ocpi` | `http://citrineos-ocpi:8085/ocpi` | OCPI |
| `http://127.0.0.1:18083` | `http://mock-msp:8083` | 공식 mock eMSP |
| `http://127.0.0.1:18088/health` | `http://billing:8088/health` | 모의 청구 |
| `http://127.0.0.1:18090` | `http://graphql-engine:8080` | Hasura 로컬 검사 |

OCPP 수신 포트의 보안 프로파일은 pinned 서버 설정/Swagger로 확인합니다. 개발용 비TLS 연결을 운영 보안 검증으로 해석하지 않습니다.

`MOCK_MSP_CONTROL_SECRET`를 설정했으므로 upstream dashboard가 제어 API를 호출할 때 헤더가 없으면 거절될 수 있습니다. 진단/증거 수집은 동봉 스크립트를 사용합니다. 제어 API 보호를 끄거나 외부에 노출하지 않습니다.

Billing만 Docker로 독립 실행하려면:

```bash
python3 scripts/init_env.py
docker compose -f compose.billing.yml up -d --build
python3 scripts/billing_client.py health
```

독립 Billing 구성과 전체 스택은 모두 호스트 18088을 사용하므로 동시에 기동하지 않습니다. 독립 구성은 `docker compose -f compose.billing.yml down`으로 정지하되 볼륨은 보존합니다.

## 3. 기존 EVerest 연결 — 진단 후 정확한 파일에서 변경

기존 EVerest compose 프로젝트 전체를 새 버전으로 교체하지 않습니다. manager의 네트워크 및 해당 버전의 OCPP 설정을 확인합니다.

- 프로토콜 목표: **OCPP 2.0.1**. 최신 예제 명령의 기본 2.1을 그대로 쓰지 않습니다.
- 충전기 ID: 팀 기준값 하나로 고정하고 CitrineOS에 같은 ID를 등록합니다. 공식 예제 값은 `cp001`이지만 팀 환경이 그렇다고 가정하지 않습니다.
- 동일 Docker 네트워크를 사용하면 후보 CSMS 주소: `ws://citrine:8081/<station-id>`.
- 컨테이너 안의 `localhost`는 Windows/WSL 호스트나 다른 컨테이너가 아닙니다.
- 호스트의 loopback 전용 18081 포트가 컨테이너에서 `host.docker.internal`로 반드시 연결된다고 가정하지 않습니다. 권장 방식은 manager를 실험 네트워크에도 연결하고 내부 DNS를 쓰는 것입니다.
- `OCPP201` DB 설정과 `OCPPmulti` 설정 구조는 버전에 따라 다릅니다. 임의 환경변수 `CSMS_URL`만 추가하면 작동한다고 가정하지 않습니다.

**진단 후 사용하는 연결 예시**(실제 컨테이너명을 먼저 확인):

```bash
# 임시 진단용 네트워크 연결. 기존 기본 네트워크는 제거하지 않음.
docker network connect coop-sil-billing-net <실제-manager-컨테이너명>
```

재현 가능한 팀 배포에서는 같은 추가 네트워크를 EVerest용 별도 compose override에 명시합니다. 최초 성공 전에는 기존 compose를 덮어쓰지 않습니다. 실제 연결 파일·키를 확정하기 전 이 패키지가 기존 설정을 자동 변경하지 않는 이유입니다.

OCPP 연결 성공 기준은 `BootNotification` 수락 + 올바른 station identity + 정상 세션 `TransactionEvent`가 저장되는 것입니다. 단순 TCP 연결만으로 완료 판정하지 않습니다.

## 4. PnC 별도 게이트

정상 OCPP 수집을 먼저 확인한 다음, 기존 팀의 ISO 15118-2 PnC 실험 설정·테스트 PKI를 연결합니다. 이 패키지는 외부 인증기관 연결을 기본으로 켜지 않습니다.

반드시 확인할 연결:

```text
EV 계약 인증서/eMAID
→ ISO 15118 PnC 인증 완료 로그
→ OCPP idToken / transactionInfo.transactionId
→ OCPI session_id / cdr_token / CDR id
→ eMSP 고객 계정
```

RFID, remote start, 인증 생략으로 성공한 실험은 PnC 결과로 적지 않습니다. PnC 실패를 숨기기 위해 Allow-all 인증을 켜지 않습니다.

## 5. CDR 수신 → Billing

정상 세션이 종료되면 CDR 원문이 공식 mock-msp에 도착하는지 확인합니다. `/_mock/state/cdrs`에는 CDR 객체 맵이 반환됩니다. Core/OCPI가 CDR을 생성하지 않았다면 Billing을 우회해 가짜 값을 넣고 종단 간 성공이라고 기록하지 않습니다.

```bash
python3 scripts/collect_evidence.py --include-wire
python3 scripts/billing_client.py sync
python3 scripts/billing_client.py invoices
python3 scripts/billing_client.py events
```

`sync`는 mock eMSP 상태를 **GET으로만** 읽고 Billing 원장에 명세를 만듭니다. 응답 `count=0`은 성공 증거가 아닙니다. 자동 무한 polling은 넣지 않았습니다. 세션별 증거를 명확하게 보존하기 위해 실행 시점에 호출합니다.

기본 retail policy는 테스트 RFID 계약 하나만 등록합니다. 실제 수신한 PnC `cdr_token`이 다르면 `HELD/UNKNOWN_CONTRACT`로 보류됩니다. 팀이 승인한 계약 식별값을 정책 파일에 등록하고 Billing 이미지를 다시 빌드합니다. 계약을 확인하지 않고 모든 사용자에게 같은 계정을 자동 배정하지 않습니다.

고객 가격은 `total_energy[kWh] × 소매 단가`입니다. CDR `total_cost`는 별도 보관하고 고객 청구액으로 그대로 복사하지 않습니다. KRW/USD/EUR 단가는 각각 독립적인 **합성 테스트 요금**이며 환율을 뜻하지 않습니다. 세금·할인·주차·시간 요금은 제외했습니다.

`SIMULATED_INVOICE_NOT_PAID`는 모의 청구 명세이며 결제 승인·결제 영수증이 아닙니다.

## 6. GitHub 팀 배포 게이트

패키지를 새 팀 환경 저장소의 기반으로 사용합니다. 대상 저장소가 정해지기 전 자동 push하지 않습니다.

```bash
# 저장소를 새로 만들거나 기존 저장소의 별도 브랜치에서, 검토 후 실행
# git init
# git switch -c env/sil-billing-v0.1
# git add README.md docs billing config fixtures tests scripts deploy \
#   compose.billing.yml UPSTREAM.lock.json .gitignore .gitattributes .github
# git diff --cached --stat
# git commit -m "Add reproducible SIL billing lab candidate"
# git remote add origin <확정한 팀 저장소 URL>
# git push -u origin env/sil-billing-v0.1
```

업로드 전 `.env`, 인증서 개인키, 실제 결제 키, 계정정보, raw 세션 로그가 staged 파일에 없는지 확인합니다. 공개 테스트 인증서라도 개인키는 실험 목적·범위·만료 정책을 검토한 뒤 별도 관리합니다.

구성 완료 후 `stack.sh lock-images` 결과 및 실제 EVerest 커밋/이미지 digest를 팀의 최종 lock 문서에 반영합니다. 새 팀원이 clone한 깨끗한 환경에서 정상 PnC 세션 1건을 재현한 뒤에만 `env-ready` 태그를 붙입니다.

## Windows VS Code 최근 폴더도 함께 확인하기

기존 EVerest VS Code의 WSL 터미널에서:

```bash
bash /path/to/coop-sil-billing/scripts/audit_from_wsl.sh
```

이 스크립트는 가능한 경우 Windows의 `%APPDATA%/Code/User/globalStorage/state.vscdb`를 읽기 전용으로 열고, `everest/citrine/coop/ev-pnc`가 포함된 최근 항목만 보고서에 넣습니다. 접근하지 못해도 기존 환경을 수정하거나 앱을 강제 종료하지 않습니다. 출력: `~/coop-local-audit.json`.
