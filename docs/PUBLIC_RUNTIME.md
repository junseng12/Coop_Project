# 공개 배포용 EVerest runtime

## 변경 목적

기존 `ev-pnc/manager:coop-local-20261116`은 이 PC의 컨테이너 스냅샷이다. 테스트 개인키·인증서·SQLite 상태·개인 경로가 섞여 있어 공개 배포에 사용하지 않는다. 기존 이미지·컨테이너·볼륨은 삭제하지 않는다.

새 경로는 `deploy/everest-runtime/Dockerfile` → GHCR 이미지 → `deploy/everest.clean.yml`이다. GitHub Actions가 검사 후 배포하고, `IMAGES.lock.json`의 registry digest를 읽어 실행한다. 소스 저장소 공개와 GHCR 패키지 공개 여부는 별개다.

## 기반과 출처

| 항목 | 고정 입력 |
|---|---|
| 공식 demo 소스 | EVerest/everest-demo `686e370d6ed6460211b06e34a4cdf9438a22e81e` |
| 공식 manager 이미지 | `ghcr.io/everest/everest-demo/manager@sha256:9165d0937323ae61ee2e496f68f3c4a465ed9099740e489df1f0161265492756` |
| amd64 manifest | `sha256:a3ff46830a1917645cee6b5146b3d4d1faa7912a7ff8b31298478251c403c4af` |
| Core 소스 revision | `c86cd9c0ada60b5797f574fd484eae4d8330017d` (2025.10.0 기반) |
| 새 OS 기반 | `debian@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc` |
| OS 패키지 저장소 | Debian snapshot `20260201T000000Z` |
| Python 추가 패키지 | `deploy/everest-runtime/requirements.txt`의 버전 고정 목록 |
| 지원 플랫폼 | 현재 빌드·실행 검증 대상 `linux/amd64` |

공식 manager의 `/usr/bin/python3.11`, `/usr/bin/openssl`, 일부 OS 공유 라이브러리는 조사 시 0바이트였다. 따라서 공식 이미지의 OS를 상속하지 않고, 새 Debian OS에 필요한 패키지를 설치한 뒤 `/ext/dist`의 EVerest runtime만 추출한다.

기존 정상 실행 이미지와 공식 이미지의 manager·EvseManager·OCPP201 바이너리 및 PyEvJosev module.py SHA-256이 동일함을 확인했다. 개인 복구 컨테이너에서 프로그램을 추출해 배포하지 않는다.

**빌드 범위:** 이 Dockerfile은 고정 공식 바이너리에서 실행 이미지를 재구성한다. EVerest C++를 소스에서 전부 재컴파일한 결과라고 주장하지 않는다. 원본 전체 빌드 절차는 위 demo 커밋의 `manager/Dockerfile`, `initial-install.sh`, `demo-patch-scripts/`에 있다. 그 상위 빌드는 일부 외부 의존성을 동적으로 해석하므로 완전한 소스 재빌드 검증은 별도 작업이다.

## 변경 목록

1. 공식 이미지는 추출 전용 stage로만 사용한다.
2. 새 Debian에서 OS runtime과 버전 고정 Python 패키지를 구성한다.
3. `sanitize.py`가 인증서·개인키·키스토어·SQLite DB·호스트 식별자 등을 제거한 최종 rootfs를 만든다.
4. 최종 이미지는 `FROM scratch`에서 그 rootfs만 복사한다. 과거 레이어에서 삭제된 개인키가 남는 방식의 배포를 하지 않는다.
5. 최초 시작 때 `/state`에서 새로운 실험 PKI를 생성한다. CA·leaf·암호는 설치 환경별로 만들어지고 재기동 시 보존한다.
6. 생성한 암호를 EvseSecurity에 연결하고 OCPP의 DB·메시지 큐·ErrorHistory를 `/state`에 저장한다.
7. 상태와 증거를 이미지 바깥에 보관한다. `/tmp`는 임시 tmpfs다.
8. 출처 정보는 이미지의 `/usr/share/coop/PROVENANCE.json`에 넣는다.

공식 demo의 기존 패치(단상 시뮬레이션, 전류 제한, Python 차량·로깅 수정 등)는 고정 바이너리 입력에 이미 포함돼 있다. 이 패키지에서 그 C++ 패치를 추가 적용했다고 주장하지 않는다.

## 이미지와 상태 분리

| 위치 | 내용 | 공개 이미지 포함 |
|---|---|---|
| 이미지 `/ext/dist` | 실행 프로그램·라이브러리·설정 템플릿 | 포함 |
| 이미지 `/opt/coop/pki-template` | 인증서 생성 코드·설정 | 포함, 생성 결과 제외 |
| 볼륨 `/state/certs`, `/state/pki` | 환경별 인증서·개인키·생성 작업물 | 제외 |
| 볼륨 `/state/ocpp` | OCPP device model·거래/큐 DB·로그 | 제외 |
| 볼륨 `/state/error_history.db` | 충전기 오류 이력 | 제외 |
| 호스트 `diagnostics/clean-everest` | 초기화·manager·OCSP·세션 증거 | 제외 |
| 백엔드 기존 named volume | CSMS DB·브로커·Billing 원장 | 제외 |

`/state/everest.yaml`에는 생성된 개인키 암호가 반영되므로 이 파일도 비공개 runtime 데이터다. 볼륨을 이미지로 commit하거나 외부에 게시하지 않는다.

## 로컬 빌드와 검사

```bash
docker build --platform linux/amd64 -t coop-lab/everest-runtime:clean-20261116 deploy/everest-runtime
python3 scripts/audit_runtime_image.py coop-lab/everest-runtime:clean-20261116 --out diagnostics/image-audit.json
```

레이어 검사는 PEM 개인키, 키스토어 확장자, SQLite 시그니처를 검사한다. 모든 임의 인코딩 비밀값까지 발견하는 보편적 비밀 탐지기는 아니다. 작은 Docker build context와 코드 검토를 함께 사용한다.

로컬 빌드를 시험할 때만 다음처럼 명시적으로 image override를 사용한다.

```bash
export EVEREST_RUNTIME_IMAGE=coop-lab/everest-runtime:clean-20261116
bash scripts/clean_everest.sh up
bash scripts/review_clean_runtime.sh
```

기존 가상 충전기가 같은 `cp001`로 연결되어 있다면 먼저 해당 실험 세션을 종료하고 manager를 중지한다. 원본 컨테이너는 삭제하지 않는다. 새 포트는 MQTT 14227 / Node-RED 14880이다. 기본 IPv6 subnet은 `fd42:4556:2026:1::/64`이며 충돌하면 `COOP_IPV6_SUBNET`으로 바꿀 수 있다.

## 공개 저장소에서 처음 시작

Docker Engine + Compose, Git, Python 3, Linux/WSL2가 필요하다. 하드웨어와 Docker 환경에 따라 추가 자원 준비가 필요하다.

```bash
git clone https://github.com/junseng12/Coop_Project.git
cd Coop_Project
bash scripts/bootstrap_public.sh
```

이 명령은 외부 공식 CitrineOS 소스를 고정 커밋으로 준비하고 백엔드를 빌드·초기화한다. 기존 DB 볼륨이 있으면 seed를 무조건 다시 실행하지 않는다. 깨끗한 GHCR runtime을 내려받아 새 `/state` 볼륨으로 시작한다.

```bash
bash scripts/clean_everest.sh status
bash scripts/clean_everest.sh start-session
# 원하는 시간 동안 충전 후 실행
bash scripts/clean_everest.sh stop-session
```

전체 자동 검증은 다음과 같다.

```bash
bash scripts/review_clean_runtime.sh
```

이 문서에서 제공하는 첫 설치 경로는 코드로 준비된 경로다. 현재 검증 기록이 '기존 백엔드 + 새 runtime/새 PKI'인지, '전체 신규 백엔드까지 포함한 설치'인지 `PUBLIC_VALIDATION.json`에서 구분한다. 완전 신규 설치나 타 PC 재현을 실행 증거 없이 완료로 표시하지 않는다.

## GHCR 배포와 고정

`publish-clean-everest` 워크플로는 수동 실행 시 테스트 → 빌드 → 레이어 검사 → runtime import 검사 → GHCR push를 수행한다. 아직 이 CI가 실제 PnC 충전을 자동 검증하는 것은 아니다.

배포 결과 artifact `published-image-lock`의 `IMAGES.lock.json`을 저장소에 반영한다. `scripts/clean_everest.sh`는 기본 경로에서 `@sha256:`가 없는 공개 이미지 참조를 거부한다. 태그 `latest`를 기준으로 실행하지 않는다.

GHCR은 최초 배포 시 private가 기본값이다. 패키지 설정에서 public으로 전환한 뒤, 로그인 정보 없는 registry 요청으로 접근이 되는지 확인해야 공개 배포 완료다.

참고: [공식 demo 소스](https://github.com/EVerest/everest-demo/tree/686e370d6ed6460211b06e34a4cdf9438a22e81e), [Docker multi-stage](https://docs.docker.com/build/building/multi-stage/), [GHCR 배포·digest](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
