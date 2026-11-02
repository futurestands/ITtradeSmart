"""Advisory-only loopback client. No imports or calls to strategy/risk/execution modules."""
import http.client
import json
import os
import socket
import threading
import time
from urllib.parse import urlsplit
from ai_contract import ContractError, MAX_BYTES, unavailable, validate, strict_json


class ServiceFailure(RuntimeError):
    def __init__(self, code):
        self.code = code


class AILabAdapter:
    def __init__(self, url=None, token=None, timeout=2):
        self.url = url
        self.token = token
        self.timeout = timeout

    def exchange(self, path, payload=None):
        connection = None
        timer = None
        expired = threading.Event()
        started = time.monotonic()
        try:
            url = self.url if self.url is not None else os.environ.get("SMARTHUB_AI_LAB_URL", "http://127.0.0.1:8765")
            token = self.token if self.token is not None else os.environ.get("SMARTHUB_AI_LAB_TOKEN", "")
            endpoint = urlsplit(url)
            if (endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1" or
                    endpoint.username or endpoint.password or endpoint.query or endpoint.fragment or
                    endpoint.path not in ("", "/") or not endpoint.port or
                    not isinstance(token, str) or len(token) < 32 or not token.isascii() or any(c.isspace() for c in token) or
                    token == os.environ.get("SMARTHUB_API_TOKEN") or not 0 < self.timeout <= 5):
                raise ServiceFailure("SERVICE_NOT_CONFIGURED")
            # Direct HTTPConnection: no proxy, DNS resolution, redirects or remote URL from caller.
            connection = http.client.HTTPConnection("127.0.0.1", endpoint.port, timeout=self.timeout)
            connection.connect()
            transport_socket = connection.sock
            remaining = self.timeout - (time.monotonic()-started)
            if remaining <= 0:
                raise ServiceFailure("SERVICE_TIMEOUT")
            def expire():
                expired.set()
                try:
                    if transport_socket is not None:
                        transport_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            # Bound the whole exchange, including trickled headers/body, not just
            # individual socket reads. The timer never launches another request.
            timer = threading.Timer(remaining, expire)
            timer.daemon = True
            timer.start()
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
            headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status != 200 or response.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                raise ServiceFailure("INVALID_SERVICE_RESPONSE")
            data = response.read(MAX_BYTES+1)
            result = strict_json(data)
            if expired.is_set() or time.monotonic()-started > self.timeout:
                raise ServiceFailure("SERVICE_TIMEOUT")
            return result
        except ServiceFailure:
            if expired.is_set():
                raise ServiceFailure("SERVICE_TIMEOUT") from None
            raise
        except (TimeoutError, socket.timeout):
            raise ServiceFailure("SERVICE_TIMEOUT") from None
        except (OSError, http.client.HTTPException):
            raise ServiceFailure("SERVICE_TIMEOUT" if expired.is_set() else "SERVICE_UNAVAILABLE") from None
        except (ValueError, TypeError, RecursionError):
            raise ServiceFailure("SERVICE_TIMEOUT" if expired.is_set() else "INVALID_SERVICE_RESPONSE") from None
        finally:
            if timer:
                timer.cancel()
            if connection:
                try:
                    connection.close()
                except OSError:
                    raise ServiceFailure("SERVICE_UNAVAILABLE") from None

    def status(self):
        code, connected = "MODEL_NOT_READY", False
        try:
            result = self.exchange("/v1/status")
            validate("health", result)
            connected = True
        except ServiceFailure as exc:
            code = exc.code
        except ContractError:
            code = "INVALID_SERVICE_RESPONSE"
        return {"schema_version": "1.0", "connection_status": "CONNECTED" if connected else "UNAVAILABLE",
                "model_status": "MODEL_NOT_READY", "model_trained": False, "model": None,
                "probability": None, "advisory_only": True, "reason_code": code,
                "explanation": "Model not trained. No predictions or trade approvals are available.",
                "execution_policy": "RESEARCH_ONLY_LOCKED", "timebase_status": "TIMEBASE_UNVERIFIED"}

    def advisory(self, request):
        validate("request", request)
        try:
            result = self.exchange("/v1/predict", request)
            validate("response", result)
            if (result["request_id"] != request["request_id"] or
                    result["prediction_timestamp_utc"] != request["prediction_timestamp_utc"] or
                    result["status"] != "UNAVAILABLE" or result["model"] is not None or
                    result["probability"] is not None or result["calibration_status"] != "not_applicable" or
                    not any(reason["code"] == "MODEL_NOT_READY" for reason in result["reasons"])):
                raise ContractError("MODEL_NOT_APPROVED_OR_RESPONSE_UNBOUND")
            # Never relay arbitrary upstream instructions/explanations. Phase 1
            # can return only our contract-compliant, explicit not-ready refusal.
            return unavailable(request)
        except ServiceFailure as exc:
            return unavailable(request, exc.code)
        except ContractError:
            return unavailable(request, "INVALID_SERVICE_RESPONSE")
