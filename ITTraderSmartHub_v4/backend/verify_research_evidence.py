"""Verify captured file integrity/structure without MT5, network or trading access."""
import csv
import hashlib
import json
from pathlib import Path
from bot.market_data import Candle, MarketDataManager


def verify():
    root = Path(__file__).parent
    manifest = json.loads((root / "evidence/data_quality.json").read_text(encoding="utf-8"))
    checked, excluded = [], []
    for name, record in manifest.items():
        path = root / name if name.startswith("eurusd") else root / "evidence" / name
        data = path.read_bytes()
        raw_matches = hashlib.sha256(data).hexdigest() == record["sha256_file"]
        canonical_matches = ("canonical_lf_sha256" in record and
                             hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == record["canonical_lf_sha256"])
        if not raw_matches and not canonical_matches:
            raise ValueError("File hash mismatch: " + name)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != record["rows"]:
            raise ValueError("Row count mismatch: " + name)
        candles = [Candle(name, row["time_utc"], *(float(row[k]) for k in
                          ("open", "high", "low", "close")),
                          float(row.get("volume", row.get("tick_volume"))),
                          float(row.get("spread", row.get("spread_points")))) for row in rows]
        MarketDataManager.validate_dataset(candles)
        (excluded if "PARTIAL" in record.get("capture_status", "") else checked).append(name)
    return {"status": "VERIFIED_FILE_HASHES_AND_STRUCTURAL_CHECKS_ONLY",
            "checked": checked, "excluded_partial_captures": excluded,
            "limitations": "No proof of completeness, economic comparability or strategy performance"}


if __name__ == "__main__":
    result = verify()
    (Path(__file__).parent / "evidence/evidence_verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
