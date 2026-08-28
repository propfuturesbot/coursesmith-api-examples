"""Minimal webhook receiver with signature verification (stdlib only).

    export COURSESMITH_WEBHOOK_SECRET=whsec_...   # from register.sh (shown ONCE)
    python examples/05_webhooks/receiver.py       # listens on :8787/hooks

Every delivery is signed:

    X-CourseSmith-Signature: t=<unix>,v1=<hex hmac_sha256(secret, "{t}.{raw_body}")>

Reject anything whose signature doesn't verify or whose timestamp is
older than 5 minutes (replay protection).
"""

import hmac
import hashlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ["COURSESMITH_WEBHOOK_SECRET"]
TOLERANCE_SECONDS = 300


def verify(signature_header: str, raw_body: bytes) -> bool:
    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    t, v1 = parts.get("t", ""), parts.get("v1", "")
    if abs(time.time() - int(t)) > TOLERANCE_SECONDS:
        return False
    expected = hmac.new(SECRET.encode(), f"{t}.".encode() + raw_body,
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        sig = self.headers.get("X-CourseSmith-Signature", "")
        try:
            ok = verify(sig, raw)
        except Exception:
            ok = False
        if not ok:
            self.send_response(400)
            self.end_headers()
            return

        event = json.loads(raw)
        job = event.get("data", {}).get("job", {})
        print(f"{event['type']}  job={job.get('job_id')}  "
              f"status={job.get('status')}  video={job.get('video_url')}")

        self.send_response(200)          # 2xx fast, or CourseSmith retries
        self.end_headers()               # (1 min / 5 min / 30 min ladder)
        self.wfile.write(b"ok")

    def log_message(self, *a):           # quiet default access log
        pass


if __name__ == "__main__":
    print("listening on http://0.0.0.0:8787/hooks")
    HTTPServer(("0.0.0.0", 8787), Hook).serve_forever()
