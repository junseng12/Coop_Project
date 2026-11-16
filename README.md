# Coop_Project — EV 충전·모의 과금 SIL 실험 환경

**배포 확인:** [공개 GHCR 이미지](https://github.com/junseng12/Coop_Project/pkgs/container/coop-everest-runtime) · [이미지 빌드·배포 CI](https://github.com/junseng12/Coop_Project/actions/runs/43838732712) · [고정 digest](IMAGES.lock.json). 비로그인 다운로드 및 내려받은 배포본의 PnC→CDR→모의 청구 검증을 완료했습니다. 기존 백엔드를 재사용한 검증이며, 전체 신규 설치 검증과는 구분합니다.

가상 차량의 **ISO 15118-2 PnC 인증 → EVerest 충전 → OCPP 2.0.1 거래 → OCPI 2.2.1 CDR → mock eMSP → 모의 고객 청구**를 관찰하는 로컬 실험 환경입니다.

실제 전력 계측·생산 PKI·Stripe/실제 결제·계량 서명 검증은 포함하지 않습니다. 청구 상태는 `SIMULATED_INVOICE_NOT_PAID`입니다.

## 현재 공개 배포 경로

```text
공식 이미지 digest + 날짜 고정 Debian 패키지 + Python 버전 목록
                         ↓ Dockerfile
             깨끗한 EVerest 실행 이미지 (GHCR)
                         ↓ Compose: digest 고정
       /state 볼륨에 새 테스트 PKI·OCPP 상태 생성
                         ↓
             CitrineOS / OCPI / Mock Billing
```

기존 복구 컨테이너를 `docker commit`한 이미지와 그 개인키를 배포하지 않습니다. 공식 EVerest 바이너리의 출처를 고정하고, 별도 OS runtime을 구성하는 multi-stage 빌드입니다. C++ 전체 소스 재컴파일과는 구분합니다.

## 문서

- [공개 runtime의 출처·빌드·상태 분리·사용법](docs/PUBLIC_RUNTIME.md)
- [실제로 수행한 검증 범위](docs/PUBLIC_VALIDATION.json)
- [환경 구성과 역할 설명](docs/ENVIRONMENT_SUMMARY_AND_MANUAL_REVIEW.md)
- [기존 PC용 상세 파일 구성도](docs/FILE_MAP.md)
- [연구·환경 인계 완료 조건](docs/RESEARCH_AND_ACCEPTANCE.md)

`docs/DIRECT_REVIEW.md` 등 과거 문서는 작성자 PC에 남은 기존 runtime을 대상으로 합니다. 새 공개 이미지는 **이 README와 PUBLIC_RUNTIME.md**를 기준으로 사용하세요.

## 요구 환경

- Linux/WSL2, Docker Engine + Compose 플러그인, Git, Python 3
- 현재 검증 플랫폼: Linux amd64. 실제 차량·충전기 불필요
- IPv6 가능한 Docker bridge 및 수 GB 이상의 메모리 여유
- 백엔드 소스 빌드는 이미지 다운로드보다 더 많은 시간·디스크·메모리가 필요할 수 있음
- 새 Git clone에 기존 개인키·DB·거래 데이터는 포함되지 않음

## 시작

```bash
git clone https://github.com/junseng12/Coop_Project.git
cd Coop_Project
bash scripts/bootstrap_public.sh
```

GHCR runtime은 `IMAGES.lock.json`의 digest를 사용합니다. 비공개 패키지 상태에서는 권한이 필요하므로 패키지 공개 상태와 다운로드 가능 여부도 검증 기록에서 확인하세요.

이 설치 스크립트는 새로운 백엔드를 구성하는 경로를 제공합니다. **전체 신규 백엔드/다른 PC에서의 설치 검증 완료 여부는 PUBLIC_VALIDATION.json에 별도로 표시합니다.** 기존 DB 볼륨이 있으면 자동 재seed하지 않습니다.

## 충전 제어

```bash
bash scripts/clean_everest.sh status
bash scripts/clean_everest.sh start-session
# 원하는 충전 시간만큼 기다린 뒤
bash scripts/clean_everest.sh stop-session
```

전체 검증 자동 실행:

```bash
bash scripts/review_clean_runtime.sh
```

출력된 `diagnostics/clean-review-<UTC>/result.html` 또는 `review-summary.json`을 읽습니다. 별도 PnC 증거와 delivery 검사가 통과해야 합니다. `verify_backend.py` 단독의 PnC false는 해당 검사기의 API/DB/wire 범위를 뜻합니다.

같은 `cp001`로 기존 충전기 manager가 실행 중이면 먼저 세션을 종료하고 해당 manager를 중지하세요. 이 프로젝트는 기존 workspace를 삭제하지 않습니다.

## 상태·인증서·로그

| 위치 | 의미 |
|---|---|
| Docker `coop-everest-clean_everest-state` | 환경별 개인키·테스트 인증서·OCPP DB·큐·오류 이력 |
| 기존 backend named volumes | CSMS 데이터·브로커·Billing 원장 |
| `diagnostics/clean-everest` | 현재 manager·OCSP·세션 로그 |
| `diagnostics/clean-review-*` | 검사 결과 |
| `evidence/<UTC>` | 수신 CDR·청구 등 API 원문 수집 |

`clean_everest.sh stop`은 볼륨을 삭제하지 않습니다. 개인키와 비밀값은 각 설치에서 생성합니다. `/state` 볼륨, `.env`, raw 로그는 공개하지 않습니다. mock eMSP의 메모리 wire 기록은 재시작 시 사라지므로 실험마다 파일로 수집합니다.

## 빌드와 공개 배포

```bash
docker build --platform linux/amd64 -t coop-everest:local deploy/everest-runtime
python3 scripts/audit_runtime_image.py coop-everest:local --out diagnostics/image-audit.json
```

GitHub Actions의 `publish-clean-everest`를 실행하면 테스트·빌드·모든 레이어 검사 후 GHCR에 배포하고 digest lock artifact를 생성합니다. `IMAGES.lock.json`은 확인된 registry digest로 갱신합니다. CI의 Python 테스트/이미지 검사는 실제 PnC 연동 검증과 구분합니다.

## 알려진 제한

- EVerest는 고정 공식 바이너리 기반의 재구성 빌드이며 완전한 소스 재컴파일 검증은 아님
- 현재 clean-runtime PnC E2E는 기존 CitrineOS DB를 재사용한 시험; 전체 신규 설치 증거와 구분
- 인증서 상태 관리 중 SECC OCSP 갱신 경고가 남을 수 있음; 계약 인증 수락과 전체 PKI 관리 정상 여부는 별개
- 전체 이미지 digest 고정 배포와 소스 version 고정은 다름. 현재 lock의 범위를 확인
- 계량값의 현실 참값·상용 eMSP 동작·금융 정산에 대한 결론을 제공하지 않음

공식 소스·라이선스 안내는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 확인하세요. 공개 runtime은 해당 upstream 바이너리를 재배포하므로 설치된 라이선스 고지와 원본 소스 링크를 보존합니다.
