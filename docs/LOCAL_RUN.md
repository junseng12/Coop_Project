# 로컬 실행과 검증

이 패키지는 기존 EVerest를 보존하고 별도 백엔드를 추가합니다. 현재 작성 환경에서는 사용자의 WSL 파일과 Docker Engine에 접근할 수 없습니다. 따라서 기존 EVerest가 올바르게 구성되었는지는 아직 판정하지 않았습니다.

## 1. 기존 환경부터 확인

Windows 다운로드 폴더에서 ZIP을 풀어 `coop-sil-billing` 폴더를 만듭니다. 그 폴더에서 터미널(PowerShell)을 열고 실행합니다.

~~~powershell
.\Run-CoopLab.cmd audit
~~~

기본 WSL 배포판에서 읽기 전용 진단을 실행합니다. 결과는 패키지 안의 `diagnostics/local-audit.json`입니다. WSL의 기본 배포판이 기존 Ubuntu가 아니면 다음처럼 원하는 배포판을 지정합니다(설치된 이름 사용).

~~~powershell
wsl -d Ubuntu --exec bash scripts/run_local.sh audit
~~~

WSL 터미널에서는 패키지 폴더로 이동한 뒤 다음 명령을 사용합니다.

~~~bash
bash scripts/run_local.sh audit /home/hyebin/research/ev-pnc
~~~

명시한 경로가 없으면 새 EVerest를 만들지 않고 경로 부재를 기록합니다. 진단은 Git 커밋·변경 파일명, Compose 경로, 이미지 ID·마운트, 접근 가능한 VS Code 최근 작업 정보를 확인합니다. 실행 중인 EVerest manager를 찾으면 알려진 PnC 실행 스크립트 존재 여부와 OCPP device model의 버전·대상 호스트도 읽기 전용으로 확인합니다. SQLite 구조가 다르면 추측하지 않고 미확인으로 남깁니다. .env·개인키·컨테이너 Env는 보고서에 넣지 않습니다.

**이 진단 보고서를 먼저 검토해야 기존 EVerest 연결 설정을 정확히 수정할 수 있습니다.** 현재는 기존 설정 파일을 자동 덮어쓰거나 충전 세션을 강제로 시작하지 않습니다.

## 2. 별도 백엔드 구성

Docker Desktop이 실행 중이고 해당 WSL 배포판에서 `docker info`가 성공해야 합니다. Git·Python 3.10+·Compose 2.24.4+가 필요합니다.

~~~powershell
.\Run-CoopLab.cmd backend
~~~

이 명령은 기존 환경 진단 → 로컬 인증값 생성 → 고정 커밋 다운로드 → Compose 검증 → 새 백엔드 빌드·기동 → 준비 상태 대기 → 새 실험 DB 초기 데이터 등록 → 실제 API 검사 순서로 실행합니다. 첫 빌드는 시간이 걸립니다. Docker가 없으면 BLOCKED로 종료하며 기존 환경은 수정하지 않습니다.

새 프로젝트 이름은 `coop-sil-billing`입니다. 기존 EVerest·MaEVe 컨테이너를 정지하거나 DB·볼륨을 삭제하지 않습니다. 초기 데이터 등록은 이 별도 프로젝트 DB에만 적용합니다. 기존에 같은 이름의 실험 스택을 사용했다면 해당 데이터가 실험용인지 먼저 확인합니다.

`backend` 성공은 서버와 초기 데이터 준비를 뜻합니다. 실제 충전 세션 성공이나 PnC 인증 성공을 뜻하지 않습니다.

## 3. 실제 충전 후 연결 검사

실제 EVerest 설정은 먼저 진단 결과를 검토한 뒤 docs/SETUP.md의 네트워크·OCPP 단계에 맞춰 연결합니다. EVerest를 자동으로 최신 이미지로 교체하지 않습니다. 정상 PnC 세션을 종료한 뒤:

~~~powershell
.\Run-CoopLab.cmd check
~~~

검사는 모의 eMSP가 수신한 CDR을 Billing으로 동기화하고 다음 근거를 대조합니다.

- CSMS의 종료된 transactionId = CDR session_id
- 공식 eMSP의 POST 수신 기록, HTTP·OCPI 응답, 스키마 검증 통과
- 수신 CDR과 Billing 청구 명세의 SHA256 및 session_id 일치
- Billing의 입력 출처가 수신 CDR snapshot인지 확인

수신 객체가 비어 있거나, 스키마 검증에 실패했거나, 청구 명세가 합성 수동 입력에서 만들어졌으면 데이터 연결 성공으로 표시하지 않습니다. 새 실행만 보려면 WSL에서 `python3 scripts/verify_backend.py --sync --since <ISO8601-시작시각>`을 사용합니다. 기록 조회는 최근 1,000건으로 제한되므로 오래된 기록은 별도 분석이 필요합니다.

결과는 `diagnostics/backend-verification.json`입니다. `DATA_CHAIN_OBSERVED`도 PnC 인증을 자동 입증하지 않습니다. ISO 15118 계약 인증서 검증과 eMAID→OCPP→CDR 계약 매핑을 별도로 확인해야 합니다. 모의 청구는 결제 완료 영수증이 아닙니다.

## 4. Docker 없이 재현하는 검증 범위

공식 mock eMSP와 Billing 사이의 HTTP 검증은 아래처럼 실행합니다. Node 24.16+ 및 Corepack/pnpm이 필요합니다.

~~~bash
python3 scripts/prepare_upstream.py
cd vendor/citrineos-core
corepack pnpm --filter @citrineos/mock-msp... install --frozen-lockfile
corepack pnpm --filter @citrineos/mock-msp... build
cd ../..
python3 scripts/check_mock_billing.py
~~~

의존 패키지까지 포함하는 `...`를 빌드 명령에서 생략하면 런타임 alias가 정리되지 않을 수 있습니다. 검사는 임시 로컬 프로세스·임시 원장만 사용하며, 기존 mock 상태에 합성 CDR을 주입하지 않습니다. 이 검사는 EVerest·CSMS·PnC 전체 검증을 대체하지 않습니다.

