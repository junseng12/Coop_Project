#!/usr/bin/env python3
"""Local live console: serves dashboard/index.html AND runs the real M2 network
MITM attack on the live stack when the dashboard's live button is pressed,
streaming real-time captured values (true vs tampered energy) back to the page.

Run:   python3 scripts/live_console.py      then open  http://127.0.0.1:18099
The dashboard auto-detects this server and enables the 🔴 live button.
"""
import json, os, subprocess, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "dashboard" / "index.html"
PORT = int(os.getenv("LIVE_PORT", "18099"))
MGR = "coop-everest-clean-manager-1"
DB = "coop-sil-billing-ocpp-db-1"
COMPOSE = ["docker", "compose", "--project-name", "coop-everest-clean",
           "--project-directory", str(ROOT), "-f", str(ROOT / "deploy/everest.clean.yml")]

LOCK = threading.Lock()
STATE = {"running": False, "done": False, "events": [], "metrics": {}, "seq": 0}

def now(): return datetime.now(timezone.utc).strftime("%H:%M:%S")
def sh(cmd, timeout=60):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception as e: return f"__ERR__ {e}"

def emit(kind, text):
    with LOCK:
        STATE["seq"] += 1
        STATE["events"].append({"t": now(), "kind": kind, "text": text})

def metrics(**kw):
    with LOCK:
        STATE["metrics"].update(kw); STATE["seq"] += 1

def mqtt_pub(topic, msg):
    sh(COMPOSE + ["exec", "-T", "mqtt-server", "mosquitto_pub", "-h", "127.0.0.1", "-q", "1", "-t", topic, "-m", msg], timeout=20)

def pm_true_kwh():
    out = sh(COMPOSE + ["exec", "-T", "mqtt-server", "mosquitto_sub", "-h", "127.0.0.1", "-C", "1", "-W", "3",
                        "-t", "everest_external/nodered/1/powermeter/totalKWattHr"], timeout=8)
    try: return float(out)
    except: return None

def rewrites():
    out = sh(["docker", "logs", "ocpp-mitm"], timeout=10)
    return out.count("rewrote meterValue") if "__ERR__" not in out else 0

def db_latest(since):
    out = sh(["docker", "exec", DB, "psql", "-U", "citrine", "-d", "citrine", "-At", "-F", "|", "-c",
              f"SELECT \"transactionId\",\"totalKwh\" FROM \"Transactions\" WHERE \"createdAt\">'{since}' ORDER BY \"createdAt\" DESC LIMIT 1;"], timeout=10)
    if not out or "__ERR__" in out or "|" not in out: return None, None
    tid, kwh = out.split("|")[:2]
    try: return tid, float(kwh)
    except: return tid, None

def run_dir():
    dirs = sorted(ROOT.glob("diagnostics/live-m2-*"))
    return dirs[-1] if dirs else None

def live_attack():
    try:
        rd = run_dir()
        if not rd:
            emit("err", "diagnostics/live-m2-* 재현 폴더가 없습니다."); return
        emit("step", "① 중간자 프록시 기동 + EVerest 리다이렉트 (약 1분, 매니저 재시작)")
        out = sh(["bash", str(rd / "mitm_up.sh")], timeout=180)
        if "charger connected" in out or "listening" in out:
            emit("ok", "프록시 가동 · EVerest가 프록시를 통해 서버에 연결됨")
        else:
            emit("warn", "프록시 기동 로그 확인 중...")
        since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        emit("step", "② 충전 세션 시작 (ISO 15118 · PnC 인증 · 전력 인출)")
        mqtt_pub("everest_external/nodered/1/carsim/cmd/execute_charging_session",
                 "sleep 1;iso_wait_slac_matched;iso_start_v2g_session ac,-1,-1;iso_wait_pwr_ready;iso_draw_power_regulated 16,3;sleep 120")
        emit("charge", "충전 중 — 충전기 실측(참) vs 서버 저장(변조)을 실시간 추적")
        last_rew = 0
        for i in range(22):  # ~50s of charging
            time.sleep(2.3)
            true = pm_true_kwh()
            rew = rewrites()
            tid, stored = db_latest(since)
            m = {}
            if true is not None: m["true_kwh"] = round(true, 4)
            if stored is not None: m["stored_kwh"] = round(stored, 4)
            m["rewrites"] = rew
            if true and stored and stored > 0: m["ratio"] = round(true / stored, 1)
            metrics(**m)
            if rew > last_rew:
                emit("evt", f"⚡ 중간자 변조 발생 #{rew}: meterValue ×0.1")
                last_rew = rew
        emit("step", "③ 충전 종료 → 거래 확정")
        mqtt_pub("everest_external/nodered/1/carsim/cmd/modify_charging_session",
                 "iso_stop_charging;iso_wait_v2g_session_stopped;unplug")
        time.sleep(14)
        rew = rewrites(); tid, stored = db_latest(since); true = pm_true_kwh()
        m = {"rewrites": rew}
        if true is not None: m["true_kwh"] = round(true, 4)
        if stored is not None: m["stored_kwh"] = round(stored, 4)
        if true and stored and stored > 0: m["ratio"] = round(true / stored, 1)
        metrics(**m)
        emit("evt", f"⚡ 최종: 중간자 변조 {rew}회 (Ended meterValue 포함)")
        if true is not None and stored is not None:
            emit("result", f"충전기 실측 {true:.4f} kWh → 서버 저장 {stored:.4f} kWh  (≈{m.get('ratio','?')}× 축소) · 거래 {tid}")
        # bill it
        token = ""
        envf = ROOT / ".env"
        if envf.is_file():
            for ln in envf.read_text().splitlines():
                if ln.startswith("BILLING_API_TOKEN="): token = ln.split("=", 1)[1]
        sh(["python3", str(ROOT / "scripts/verify_backend.py"), "--sync", "--since", since,
            "--out", str(rd / "live_console_delivery.json")], timeout=60)
        emit("step", "④ 청구서 발행 — 변조된 값으로 과금됨")
    except Exception as e:
        emit("err", f"오류: {e}")
    finally:
        emit("step", "⑤ 원복 중 (EVerest 직결 복구 · 프록시 제거)")
        rd = run_dir()
        if rd: sh(["bash", str(rd / "mitm_down.sh")], timeout=180)
        emit("ok", "원복 완료 — 라이브 공격 종료. 스택 정상.")
        with LOCK: STATE["running"] = False; STATE["done"] = True; STATE["seq"] += 1

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store"); self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            try: self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            except Exception as e: self._send(500, str(e), "text/plain")
        elif p == "/api/live/ping":
            self._send(200, json.dumps({"live": True}))
        elif p == "/api/live/state":
            with LOCK: self._send(200, json.dumps(STATE))
        else:
            self._send(404, json.dumps({"error": "not_found"}))
    def do_POST(self):
        if self.path.split("?")[0] == "/api/live/start":
            with LOCK:
                if STATE["running"]:
                    self._send(200, json.dumps({"ok": False, "reason": "already_running"})); return
                STATE.update({"running": True, "done": False, "events": [], "metrics": {}, "seq": 0})
            threading.Thread(target=live_attack, daemon=True).start()
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not_found"}))

if __name__ == "__main__":
    print(f"Live console: http://127.0.0.1:{PORT}  (dashboard + 🔴 live M2 attack)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
