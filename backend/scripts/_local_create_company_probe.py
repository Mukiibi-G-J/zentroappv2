"""Create a company on LOCAL API and poll task status with timings."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "http://127.0.0.1:8002/api"
NAME = f"localtest{datetime.now(timezone.utc).strftime('%H%M%S')}"


def post(path: str, body: dict) -> tuple[int, dict | str]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def get(path: str) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        f"{API}{path}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main() -> None:
    print(f"API={API}", flush=True)
    print(f"company={NAME}", flush=True)
    t0 = time.perf_counter()
    status, body = post(
        "/company/create-company-account/",
        {
            "companyName": NAME,
            "companyEmail": f"{NAME}@example.com",
            "companyPhone": "+256700000077",
            "companyAddress": "Kampala Test Street",
            "companyCountry": "Uganda",
            "fullName": "Local Test User",
            "password": "TestPass1!",
            "organization_size": "1-10",
            "business_category": "1",
            "business_objective": "1",
            "subscription": {"plan": "Free Trial", "price": 0, "yearlyPrice": 0},
        },
    )
    print(
        f"enqueue status={status} elapsed={time.perf_counter()-t0:.1f}s body={body}",
        flush=True,
    )
    if status >= 400 or not isinstance(body, dict) or not body.get("task_id"):
        return

    task_id = body["task_id"]
    last = None
    while True:
        time.sleep(2)
        st, info = get(f"/company/task-status/{task_id}/")
        elapsed = time.perf_counter() - t0
        if not isinstance(info, dict):
            print(f"[{elapsed:6.1f}s] status_http={st} raw={info!r}", flush=True)
            continue
        key = (
            info.get("state"),
            info.get("progress"),
            info.get("status"),
            info.get("message"),
        )
        if key != last:
            print(f"[{elapsed:6.1f}s] {json.dumps(info)[:600]}", flush=True)
            last = key
        if info.get("state") in ("SUCCESS", "FAILURE"):
            print(f"DONE in {elapsed:.1f}s", flush=True)
            result = info.get("result") if isinstance(info.get("result"), dict) else {}
            print(
                "used_template_baseline=",
                info.get("used_template_baseline", result.get("used_template_baseline")),
                flush=True,
            )
            print(
                "login_url=",
                info.get("login_url") or result.get("login_url"),
                flush=True,
            )
            print(f"expected_dev_login=http://{NAME}.localhost:3000/login", flush=True)
            break
        if elapsed > 600:
            print("TIMEOUT 10m", flush=True)
            break


if __name__ == "__main__":
    main()
