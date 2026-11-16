# Repository guardrails

- Preserve any existing EVerest workspace. No global upgrades, forced checkout, prune or volume deletion.
- Read UPSTREAM.lock.json and docs/VERIFICATION.md before asserting compatibility.
- Docker stack files are source-reviewed candidates until a real local E2E run is recorded.
- Keep OCPP 2.0.1 distinct from CitrineOS project version 2.1.0 and OCPI 2.2.1.
- Do not substitute RFID/remote-start/fixture evidence for PnC certificate authentication.
- Do not call billing statements paid receipts. There is no payment implementation here.
- Never commit .env, real API keys, private certificates, raw customer logs or vendor trees.
- Test with: python3 -m unittest discover -s tests -v; python3 -m billing.demo.
- Keep changes limited to this repository. Ask for exact target repository before pushing.
- Do not report source review or synthetic unit tests as executed EVerest/OCPI interoperability.
