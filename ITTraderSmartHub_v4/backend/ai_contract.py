"""Pinned Lab v1 schemas plus strict JSON; no model, market or trading imports."""
from datetime import datetime
from pathlib import Path
import hashlib
import json
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent / "ai_contracts"
MAX_BYTES = 16384
TARGET_UNAVAILABLE = "UNAVAILABLE_NO_REGISTERED_TARGET"


class ContractError(ValueError):
    pass


def strict_json(raw):
    def reject(*_):
        raise ContractError("INVALID_JSON")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                reject()
            result[key] = value
        return result
    try:
        if len(raw) > MAX_BYTES:
            reject()
        result = json.loads(raw, parse_constant=reject, object_pairs_hook=pairs)
        json.dumps(result, allow_nan=False)
        return result
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ContractError("INVALID_JSON") from exc


def contract_hashes():
    manifest = json.loads((ROOT / "source_manifest.json").read_text(encoding="utf-8"))["schemas"]
    for name, expected in manifest.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ContractError("CONTRACT_HASH_MISMATCH")
    return manifest


def validate(kind, payload):
    try:
        json.dumps(payload, allow_nan=False)
        contract_hashes()
        filename = {"request": "prediction_request.v1.schema.json", "response": "prediction_response.v1.schema.json",
                    "health": "health_response.v1.schema.json"}[kind]
        schema = json.loads((ROOT/filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        if not Draft202012Validator(schema).is_valid(payload):
            raise ContractError("SCHEMA_INVALID")
        if kind in ("request", "response"):
            prediction = datetime.fromisoformat(payload["prediction_timestamp_utc"].replace("Z", "+00:00"))
            if kind == "request":
                for context in payload["timeframe_context"].values():
                    if datetime.fromisoformat(context["last_closed_bar_time_utc"].replace("Z", "+00:00")) > prediction:
                        raise ContractError("FUTURE_FEATURE_TIMESTAMP")
        if kind == "health" and payload["contract_hashes"] != contract_hashes():
            raise ContractError("CONTRACT_HASH_MISMATCH")
    except (ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        raise ContractError("CONTRACT_INVALID") from exc


def unavailable(request, code="MODEL_NOT_READY"):
    messages = {
        "MODEL_NOT_READY": "Model not trained. No verified model or registered target is available.",
        "SERVICE_UNAVAILABLE": "Local AI Lab connection unavailable. No prediction is available.",
        "SERVICE_TIMEOUT": "Local AI Lab timed out. No prediction is available.",
        "INVALID_SERVICE_RESPONSE": "Local AI Lab response was rejected. No prediction is available.",
        "SERVICE_NOT_CONFIGURED": "Local AI Lab connection is not configured.",
    }
    result = {
        "schema_version": "1.0", "request_id": request["request_id"], "model": None,
        "prediction_timestamp_utc": request["prediction_timestamp_utc"], "status": "UNAVAILABLE",
        "advisory_only": True, "target_definition_id": TARGET_UNAVAILABLE, "probability": None,
        "calibration_status": "not_applicable", "input_freshness": {"max_bar_age_seconds": None},
        "validation": {"status": "FAIL", "checks": [{"name": "model_readiness", "status": "FAIL"}]},
        "reasons": [{"code": code, "message": messages[code]}],
    }
    validate("response", result)
    return result


def health():
    result = {"schema_version": "1.0", "service": "nas100-ai-lab", "lab_version": "0.1.1",
              "status": "UNAVAILABLE", "advisory_only": True, "model_ready": False,
              "model": None, "probability": None, "reason_code": "MODEL_NOT_READY", "contract_hashes": contract_hashes()}
    validate("health", result)
    return result
