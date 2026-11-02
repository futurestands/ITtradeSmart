"""Real local two-interpreter smoke test; owns/cleans only its child processes.

Synthetic protocol probe only. No prices, training, MT5 or bot-mode changes.
"""
import argparse
from datetime import datetime, timezone, timedelta
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from ai_contract import health, strict_json, validate


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request_json(port, path, token=None, payload=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, allow_nan=False).encode()
    try:
        conn.request("GET" if body is None else "POST", path, body, headers)
        response = conn.getresponse()
        return response.status, strict_json(response.read(16385))
    finally:
        conn.close()


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


def verify(lab_root, lab_python):
    root = Path(__file__).parent.resolve()
    output = root/"evidence/ai_lab_integration"
    output.mkdir(parents=True, exist_ok=True)
    lab_port, gateway_port = free_port(), free_port()
    while gateway_port == lab_port:
        gateway_port = free_port()
    local_token, master_token = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("MT5_") or key.startswith("SMARTHUB_"):
            env.pop(key)
    env.update(PYTHONDONTWRITEBYTECODE="1", SMARTHUB_AI_LAB_TOKEN=local_token,
               SMARTHUB_API_TOKEN=master_token, SMARTHUB_AI_LAB_URL="http://127.0.0.1:"+str(lab_port))
    processes = []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    logs = [(output/"lab_service.txt").open("w", encoding="utf-8"),
            (output/"gateway_service.txt").open("w", encoding="utf-8")]
    try:
        lab = subprocess.Popen([str(lab_python), "-u", str(root/"ai_lab_service.py"), "--lab-root", str(lab_root),
                                "--port", str(lab_port)], cwd=root, env=env, stdout=logs[0], stderr=subprocess.STDOUT,
                               creationflags=flags)
        processes.append(lab)
        launcher = "from app import app; app.run(host='127.0.0.1', port="+str(gateway_port)+", debug=False, use_reloader=False)"
        gateway = subprocess.Popen([sys.executable, "-u", "-c", launcher], cwd=root, env=env,
                                   stdout=logs[1], stderr=subprocess.STDOUT, creationflags=flags)
        processes.append(gateway)
        deadline = time.monotonic()+20
        while True:
            if lab.poll() is not None or gateway.poll() is not None:
                raise RuntimeError("Owned service failed to start; inspect sanitized logs")
            try:
                if request_json(lab_port, "/v1/health", local_token)[0] == 200 and request_json(gateway_port, "/health")[0] == 200:
                    break
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Owned service startup deadline exceeded")
            time.sleep(.1)
        health_code, lab_health = request_json(lab_port, "/v1/health", local_token)
        validate("health", lab_health)
        assert request_json(lab_port, "/v1/health")[0] == 401
        assert request_json(gateway_port, "/api/v5/ai/status")[0] == 401
        _, pair = request_json(gateway_port, "/api/v4/admin/pairing-code", master_token, {})
        _, enrollment = request_json(gateway_port, "/api/v4/device/enroll", payload={
            "device_id": "dev-ai-local-probe", "device_name": "Local contract smoke test", "pairing_code": pair["pairing_code"]})
        device_token = enrollment["device_token"]
        _, before = request_json(gateway_port, "/api/v5/bot/status", master_token)
        code, status = request_json(gateway_port, "/api/v5/ai/status", device_token)
        assert code == 200 and status["connection_status"] == "CONNECTED" and status["model_trained"] is False
        now = datetime.now(timezone.utc).replace(microsecond=0)
        request = {"schema_version": "1.0", "request_id": "CONNECTION_PROBE_NOT_A_TRADE",
                   "instrument": {"symbol": "EXAMPLE_NOT_MARKET_DATA", "provider": "PROTOCOL_TEST_ONLY"},
                   "prediction_timestamp_utc": now.isoformat().replace("+00:00", "Z"),
                   "candidate": {"side": "BUY", "setup_id": "CONNECTION_PROBE_ONLY", "entry_timeframe": "M15"},
                   "timeframe_context": {"M15": {"last_closed_bar_time_utc":
                       (now-timedelta(minutes=30)).isoformat().replace("+00:00", "Z"), "features": {}}},
                   "feature_set_version": "NO_MODEL_NO_MARKET_FEATURES"}
        validate("request", request)
        code, advisory = request_json(gateway_port, "/api/v5/ai/advisory", device_token, request)
        validate("response", advisory)
        assert code == 200 and advisory["probability"] is None and advisory["reasons"][0]["code"] == "MODEL_NOT_READY"
        assert request_json(gateway_port, "/api/v5/ai/advisory", device_token, dict(request, approve_trade=True))[0] == 400
        _, after = request_json(gateway_port, "/api/v5/bot/status", master_token)
        assert before == after and after["mode"] == "OFF" and after["execution_policy"] == "RESEARCH_ONLY_LOCKED"
        stop(lab)
        _, offline = request_json(gateway_port, "/api/v5/ai/advisory", device_token, request)
        validate("response", offline)
        assert offline["probability"] is None and offline["status"] == "UNAVAILABLE"
        assert offline["reasons"][0]["code"] in ("SERVICE_UNAVAILABLE", "SERVICE_TIMEOUT")
        result = {"evidence": "VERIFIED real HTTP Gateway-to-existing-Lab companion, two separate interpreters",
                  "gateway_python": sys.version.split()[0],
                  "lab_python": subprocess.check_output([str(lab_python), "-c", "import sys;print(sys.version.split()[0])"], env=env, text=True).strip(),
                  "lab_health": lab_health, "gateway_ai_status": status, "advisory": advisory,
                  "service_stopped_refusal": offline["reasons"][0]["code"], "unauthorized_http": 401,
                  "malicious_request_http": 400, "bot_state_unchanged": True,
                  "model_trained": False, "probability": None, "market_data_used": False,
                  "training_run": False, "owned_processes_stopped": True}
        (output/"real_connection.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        for process in reversed(processes):
            stop(process)
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-root", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.lab_root.resolve(), args.lab_root.resolve()/".venv/Scripts/python.exe")
    print("VERIFIED local connection; MODEL_NOT_READY; probability=null; no trading or training.")
