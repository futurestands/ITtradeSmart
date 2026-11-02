"""Python 3.12 companion for the existing Lab: loopback, authenticated, never predicts."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import os
from pathlib import Path
import json
import sys
import threading
from ai_contract import ContractError, MAX_BYTES, contract_hashes, health, strict_json, unavailable, validate


def valid_token(value):
    return isinstance(value, str) and len(value) >= 32 and value.isascii() and not any(c.isspace() for c in value)


def load_lab_runtime(root):
    """Load the installed existing Lab validator, not models or serialized artifacts."""
    root = Path(root).resolve()
    module = importlib.import_module("nas100lab.contracts_validation")
    package = importlib.import_module("nas100lab")
    if Path(module.__file__).resolve() != root/"src/nas100lab/contracts_validation.py" or package.__version__ != "0.1.1":
        raise RuntimeError("LAB_IDENTITY_MISMATCH")
    import hashlib
    for name, digest in contract_hashes().items():
        for source in (root/"contracts"/name, root/"src/nas100lab/schemas"/name):
            if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise RuntimeError("LAB_CONTRACT_MISMATCH")
    return module.validate_advisory_contract


def create_server(lab_root, token, port=8765):
    if not valid_token(token) or token == os.environ.get("SMARTHUB_API_TOKEN"):
        raise ValueError("INDEPENDENT_LOCAL_TOKEN_REQUIRED")
    lab_validate = load_lab_runtime(lab_root)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(2)  # includes idle request-line/header reads
            super().setup()

        def log_message(self, *_):
            pass  # never log headers, tokens, bodies or caller-controlled paths

        def send_json(self, status, payload):
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            self.connection.settimeout(2)
            expected_host = "127.0.0.1:" + str(self.server.server_port)
            if self.client_address[0] != "127.0.0.1" or self.headers.get("Host") != expected_host or self.headers.get("Origin"):
                self.send_json(403, {"error": "LOCAL_ACCESS_ONLY"})
                return False
            provided = self.headers.get("Authorization", "")
            if not provided.isascii() or not hmac.compare_digest(provided, "Bearer " + token):
                self.send_json(401, {"error": "UNAUTHORIZED"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path not in ("/v1/health", "/v1/status"):
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            self.send_json(200, health())

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/v1/predict":
                self.send_json(404, {"error": "NOT_FOUND"})
                return
            try:
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ContractError("INVALID_REQUEST")
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= MAX_BYTES:
                    raise ContractError("INVALID_REQUEST")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ContractError("INVALID_REQUEST")
                request = strict_json(raw)
                validate("request", request)
                lab_validate("request", request)
                response = unavailable(request)
                lab_validate("response", response)
                self.send_json(200, response)
            except (ValueError, TypeError, OSError, RecursionError):
                self.send_json(400, {"error": "INVALID_REQUEST"})

    class BoundedServer(ThreadingHTTPServer):
        def __init__(self, address, handler):
            self.slots = threading.BoundedSemaphore(8)
            super().__init__(address, handler)

        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

    server = BoundedServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab-root", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = None
    try:
        if sys.version_info[:2] != (3, 12) or not 0 <= args.port <= 65535:
            raise ValueError("PYTHON_312_REQUIRED")
        server = create_server(args.lab_root, os.environ.get("SMARTHUB_AI_LAB_TOKEN", ""), args.port)
        print("AI Lab companion listening on 127.0.0.1:" + str(server.server_port) + "; MODEL_NOT_READY", flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    except Exception:
        print("AI Lab startup failed: verify Python 3.12, Lab root, pinned contracts and independent local token.", file=sys.stderr)
        sys.exit(1)
    finally:
        if server:
            server.server_close()
