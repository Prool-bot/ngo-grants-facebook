"""Read-only production Worker checks from GitHub-hosted runner.

No credentials, Telegram calls, AI prompts, D1 mutations, POSTs or data writes.
Only two GET requests to the documented public Worker host.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WORKER = "https://ngo-grants-instant-bot.oleh-protasoff.workers.dev"
HEADERS = {
    "User-Agent": "NGO-Grants-v59-readonly-acceptance/1.0",
    "Accept": "application/json",
}


def get(path: str) -> tuple[int, bytes]:
    request = Request(WORKER + path, headers=HEADERS, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, response.read(8192)
    except HTTPError as error:
        return error.code, error.read(8192)


def main() -> int:
    # The tests MUST NOT reveal tokens, full configuration, or response bodies.
    results = []
    try:
        code, payload = get("/health")
        if code != 200:
            print(f"FAIL health: HTTP {code}")
            results.append(False)
        else:
            try:
                value = json.loads(payload)
            except (ValueError, TypeError):
                print("FAIL health: invalid JSON")
                results.append(False)
            else:
                version = str(value.get("menu_version", ""))
                if version != "5.8":
                    print(f"FAIL health: unexpected menu_version={version!r}")
                    results.append(False)
                else:
                    print("PASS public health: menu_version=5.8")
                    results.append(True)
    except (URLError, TimeoutError, OSError) as exc:
        print(f"UNVERIFIED health: {type(exc).__name__}")
        results.append(False)
    try:
        code, _ = get("/internal/pending")
        # No auth headers: the endpoint MUST deny unauthenticated access.
        if code not in (401, 403):
            print(f"FAIL internal/pending: unauthenticated HTTP {code}")
            results.append(False)
        else:
            print(f"PASS internal/pending: unauthenticated HTTP {code}")
            results.append(True)
    except (URLError, TimeoutError, OSError) as exc:
        print(f"UNVERIFIED internal/pending: {type(exc).__name__}")
        results.append(False)
    passed = all(results)
    print("READ_ONLY_WORKER_SMOKE=" + ("PASS" if passed else "NOT_CONFIRMED"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
