# 검증 기록 — 2026-11-15

이 문서는 검증 상태의 짧은 요약이다. 거래별 수치, 경로, 버전, 재현 명령은 [LOCAL_VALIDATION_2026-11-15.md](LOCAL_VALIDATION_2026-11-15.md)에 있다.

| 항목 | 실제 결과 |
|---|---|
| 패키지 Python 테스트 | 47개 PASS |
| 공식 CitrineOS Core | `4fd7599b91c2fb6e6065e7c9b94be69880cced27` checkout 및 빌드 |
| 격리 Compose 백엔드 | DB, RabbitMQ, Hasura, OCPP, OCPI, mock eMSP, Billing 모두 healthy |
| OCPP | EVerest가 `ocpp2.0.1`로 연결, BootNotification `Accepted` |
| PnC | ISO 15118-2 TLS 세션, 계약 인증서 체인 검증, OCSP, CSMS idToken/certificate 모두 `Accepted` |
| 실제 종료 거래 | `97258ded-e042-4bda-8ee8-bcedb7e8a999`, 0.068 kWh |
| OCPI 전달 | 같은 ID의 session/CDR, 실제 OCPI POST schema 검증 성공 |
| Mock Billing | 0.068 kWh × 0.30 USD/kWh = 0.02040 USD → 0.02 USD |
| 중복 CDR | 동일 CDR 재전송 후 청구서 1건 유지, `DUPLICATE` 감사 이벤트 |
| 재시작 | DB·브로커·CitrineOS·OCPI·Billing 및 EVerest 재시작 후 상태·거래·청구서 유지, Boot 재수락 |

`scripts/verify_backend.py`의 `pnc_authentication_verified: false`는 이 스크립트가 API/DB/HTTP 상관관계만 판정하고 인증서 로그를 해석하지 않도록 의도적으로 보수적으로 만든 값이다. PnC 근거는 EVerest 세션 로그, 공개 인증서 메타데이터, OCSP 로그와 CSMS 수락 기록을 함께 대조했다.

완료로 주장하지 않는 항목: 실제 결제, Stripe, 계량 서명 검증, 생산 PKI, OCPI 적합성 전체, mock eMSP 재시작 후 메모리 수신 이력 보존.
