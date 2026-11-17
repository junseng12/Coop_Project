# 충전 세션 터미널 (SIL 대시보드)

명령어로 충전 세션을 진행하고, 완충·종료 시 청구서가 생성되는 단일 HTML 대시보드입니다.
Virtual EV → EVerest → OCPP → CitrineOS → OCPI → Billing 경로를 소프트웨어로 모사하며,
M1~M4 변조 지점에서 보고 에너지를 낮췄을 때 "많이 충전·적게 청구"가 어느 계층 대조에서
탐지되는지 시각화합니다.

## 여는 방법

별도 서버·빌드 없이 **`dashboard/index.html` 파일을 브라우저로 열기만** 하면 됩니다.

- 로컬: 파일을 더블클릭하거나 브라우저에 드래그
- 또는 리포지토리 루트에서 `python3 -m http.server` 후 `/dashboard/`
- GitHub Pages로 공개하려면 저장소 Settings → Pages에서 소스를 지정하세요.

폰트(IBM Plex)는 Google Fonts에서 받아오며, 오프라인이면 시스템 폰트로 대체됩니다.
외부 스크립트·추적·네트워크 호출은 없습니다. 모든 계산은 브라우저 안에서만 수행됩니다.

## 사용 예

```
help                  명령 목록
start                 SLAC → ISO15118-2 TLS → PnC 인증 → 충전 시작 (계량 누적)
stop                  충전 종료 → OCPP Ended → OCPI CDR → 청구서 생성
                      (완충 시 SoC 100% 도달 → 자동 종료)

inject M4 5           start 전에 입력. M4(CDR 변환) 지점에서 보고 에너지를 5 kWh로 축소
start                 48 kWh 완충되어도 청구서는 5 kWh 기준으로 발행 → 변조 탐지 표시
inject off            변조 해제(정상 청구)

set currency KRW      통화 (USD|EUR|KRW)
set rate 0.30         소매 요율
set capacity 60       배터리 용량(kWh)
set soc 20            시작 SoC(%)
set amps 16 / set phases 3   전류·상 수(전력)
status / reset / clear
```

## 검증 범위와 한계

- 금액 산식은 `billing/engine.py`와 동일합니다(통화별 소수자리, ROUND_HALF_UP, `energy × rate`).
- 청구서는 `SIMULATED_INVOICE_NOT_PAID` 모의 명세입니다. **실제 결제가 아닙니다.**
- 이 대시보드는 **SIL 소프트웨어 시뮬레이션**이며, 실제 물리 계량·계량 서명·EVerest/OCPI
  상호운용 실행을 대체하지 않습니다. 라이브 스택 대상 실제 변조·증거 수집 절차는
  저장소 루트 `README.md`와 `docs/CODE_ARCHITECTURE.md`를 따르세요.
