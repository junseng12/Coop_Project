# 공식 소스 검토 기록

확인일: 2026-11-14. 실시간 연결된 GitHub 및 공식 문서를 조회했습니다. 아래 커밋은 **검토한 소스 후보**이며 전체 스택 실행 검증을 마친 배포 버전이라는 뜻이 아닙니다.

## 제공된 자료와 접근 한계

사용자가 메시지에 붙여넣은 팀 공유 요약: EVerest → CitrineOS Core/OCPI → CitrineOS Payment → Stripe 테스트, 충전·과금·결제·영수증 검증.

`EV 충전 과금 실증 구조.md`와 `.html`의 실제 원문, 기존 VS Code 작업 폴더, 기존 Git 저장소/커밋은 접근하지 못했습니다. 해당 파일을 읽었다거나 기존 PC 버전을 업데이트했다고 주장하지 않습니다.

## 검토 결과

| 항목 | 확인한 사실 | 본 패키지 결정 |
|---|---|---|
| Core main | `4fd7599b91c2fb6e6065e7c9b94be69880cced27`, 2026-10-21 커밋, v2.1.0 병합 메시지 | 정확한 commit으로 별도 checkout |
| OCPI | Core 안에 `apps/ocpi-server` 존재, Core DB/RabbitMQ/Hasura 공유 | 같은 commit 사용 |
| eMSP mock | Core 안에 `apps/mock-msp` 존재, OCPI 2.2.1, US/TST 시연 파트너 | 새 eMSP 프로토콜 서버를 만들지 않고 재사용 |
| EVerest 연결 | 공식 예제 기본 OCPP 2.1, `2.0.1` 분기 지원, PnC run script 포함 | 기존 환경 유지, OCPP 2.0.1 명시, PnC 별도 검증 |
| Payment | 별도 저장소 README에 Directus/Scan-and-charge/RabbitMQ/Stripe 설정 | 현 Core/로밍 eMSP 호환성 입증 전 기본 배포에서 제외 |
| Mock CDR | 스키마 문제를 finding으로 기록하면서 저장할 수 있음, id-keyed upsert | 저장과 과금 허용 구분 |
| PG 테스트 | Stripe 테스트는 실제 자금 이동 없는 모의 결제 | 현재 범위에서 불필요; 미연동 |

## 재현 가능한 주요 원문

- Core 커밋:
  https://github.com/citrineos/citrineos-core/commit/4fd7599b91c2fb6e6065e7c9b94be69880cced27
- Core README:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/README.md
- OCPI app:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/ocpi-server/README.md
- Mock eMSP:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/mock-msp/README.md
- Mock CDR handler:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/mock-msp/src/modules/cdrs.ts
- Mock control API:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/mock-msp/src/control/control-api.ts
- Base/local Compose:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/docker-compose.yml
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/docker-compose.local.yml
- Seed DNS patch 대상:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/ocpi-server/db/seeders/20250806120002-default-tenant-partner.ts
- EVerest example / startup:
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/ocpp-server/everest/README.md
  https://github.com/citrineos/citrineos-core/blob/4fd7599b91c2fb6e6065e7c9b94be69880cced27/apps/ocpp-server/everest/start.sh
- Payment README (moving main; not deployed):
  https://github.com/citrineos/citrineos-payment/blob/main/README.md
- OCPI CDR specification (2.2.1):
  https://github.com/ocpi/ocpi/blob/2.2.1/mod_cdrs.asciidoc
- Docker Compose merge / !override requirement:
  https://docs.docker.com/reference/compose-file/merge/
- Stripe testing:
  https://docs.stripe.com/testing

## 한계

기본 Docker 이미지에는 mutable tag가 남아 있습니다. source commit 고정과 binary/image digest 고정은 별개입니다. 설치할 PC에서 공식 빌드·시작을 확인하고 image identity를 기록한 후 팀 검증본을 확정해야 합니다. `.lock`에 빈 EVerest 정보를 임의 값으로 채우지 않습니다.
