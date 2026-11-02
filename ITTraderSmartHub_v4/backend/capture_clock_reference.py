"""Read-only network clock comparison; never sets or synchronizes Windows time."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
import socket
import struct
import time
import urllib.request


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def ntp(host):
    row = {"protocol": "NTPv4_unauthenticated", "host": host}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.settimeout(5)
            address = socket.gethostbyname(host)
            connection.connect((address, 123))
            packet = bytearray(48)
            packet[0] = 0x23
            start = time.time()
            seconds = start + 2208988800
            packet[40:48] = struct.pack("!II", int(seconds), int((seconds % 1) * 2**32))
            monotonic_start = time.monotonic()
            connection.send(packet)
            response = connection.recv(512)
            end = time.time()
            elapsed = time.monotonic() - monotonic_start
        if len(response) < 48 or response[0] & 7 != 4 or response[0] >> 6 == 3 or not 1 <= response[1] <= 15:
            raise ValueError("Invalid/unsynchronized NTP response")
        if response[24:32] != packet[40:48]:
            raise ValueError("NTP origin does not match request")
        def stamp(index):
            sec, fraction = struct.unpack("!II", response[index:index+8])
            return sec - 2208988800 + fraction / 2**32
        receive, transmit = stamp(32), stamp(40)
        if transmit < receive or abs((end-start) - elapsed) > .1:
            raise ValueError("Server/host clock changed during observation")
        offset = ((receive-start) + (transmit-end)) / 2
        delay = (end-start) - (transmit-receive)
        if delay < -.001 or delay > 5:
            raise ValueError("Implausible NTP round trip")
        row.update(status="OBSERVED", request_transmit_hex=bytes(packet[40:48]).hex(),
                   response_hex=response.hex(), local_sent_utc=iso(start), local_received_utc=iso(end),
                   server_received_utc=iso(receive), server_transmitted_utc=iso(transmit),
                   stratum=response[1], leap_indicator=response[0] >> 6,
                   offset_server_minus_windows_seconds=offset, round_trip_seconds=delay,
                   monotonic_elapsed_seconds=elapsed)
    except Exception as exc:
        row.update(status="FAILED", error_type=type(exc).__name__, error=str(exc))
    return row


def https(url):
    row = {"protocol": "HTTPS_Date_corroboration_only", "url": url}
    try:
        start, monotonic_start = time.time(), time.monotonic()
        request = urllib.request.Request(url + "?timeaudit=" + str(time.time_ns()),
                                        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        with urllib.request.urlopen(request, timeout=7) as response:
            header, age, status = response.headers.get("Date"), response.headers.get("Age"), response.status
        end = time.time()
        row.update(status="OBSERVED", local_sent_utc=iso(start), local_received_utc=iso(end),
                   server_date=header, age_header=age, http_status=status,
                   offset_from_local_midpoint_seconds=parsedate_to_datetime(header).timestamp()-(start+end)/2,
                   round_trip_seconds=time.monotonic()-monotonic_start,
                   limitations="HTTP date has one-second resolution, path delay and possible intermediary clocks; not NTP")
    except Exception as exc:
        row.update(status="FAILED", error_type=type(exc).__name__, error=str(exc))
    return row


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        calls = [pool.submit(ntp, name) for name in ("time.cloudflare.com", "time.google.com")]
        calls += [pool.submit(https, url) for url in ("https://www.cloudflare.com/cdn-cgi/trace", "https://www.google.com/generate_204")]
        result = {"observed_utc": iso(time.time()), "sources": [call.result() for call in calls],
                  "limitations": "UDP NTP is not authenticated/NTS; independent providers and HTTPS corroborate seconds-scale clock accuracy, not historical broker DST"}
    output = Path(__file__).parent / "evidence/time_integrity" / datetime.now(timezone.utc).strftime("clock_%Y%m%dT%H%M%S_%fZ.json")
    output.parent.mkdir(exist_ok=True, parents=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
