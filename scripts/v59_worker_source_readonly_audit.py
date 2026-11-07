"""Read-only Cloudflare deployed Worker contract audit.

Retrieves Worker source in memory; NEVER logs, persists, uploads or prints it.
No Telegram calls, no Cloudflare changes, no D1 queries.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

SCRIPT = "ngo-grants-instant-bot"


def inspect_source(raw: bytes) -> dict[str, bool]:
    # Cloudflare API may return a JavaScript body or multipart module bundle.
    # Byte presence is only a preflight indication, not end-to-end UI proof.
    if not raw or len(raw) > 8_000_000:
        raise RuntimeError("Unexpected Worker source size")
    return {
        "legacy_single_link": b"channel_url" in raw,
        "multiple_links_field": b"channel_urls" in raw,
        "tiers_field": b"channel_tiers" in raw,
        "v58_marker": b"5.8" in raw,
    }


def main() -> int:
    account=(os.getenv("CF_WORKER_ACCOUNT_ID") or
             os.getenv("CF_ACCOUNT_ID") or "").strip()
    token=(os.getenv("CF_WORKER_API_TOKEN") or "").strip()
    if not account or not token:
        print("CLOUDFLARE_SOURCE_AUDIT=UNVERIFIED_MISSING_READ_CREDENTIALS")
        return 2
    url=(f"https://api.cloudflare.com/client/v4/accounts/{account}"
         f"/workers/scripts/{SCRIPT}")
    req=urllib.request.Request(url,method="GET",headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/javascript, multipart/form-data, */*",
        "User-Agent":"NGO-Grants-v59-read-only-audit",
    })
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read(8_000_001)
    except urllib.error.HTTPError as e:
        print(f"CLOUDFLARE_SOURCE_AUDIT=HTTP_{e.code}")
        return 2
    except (OSError,TimeoutError,urllib.error.URLError) as e:
        print(f"CLOUDFLARE_SOURCE_AUDIT=NETWORK_{type(e).__name__}")
        return 2
    result=inspect_source(raw)
    # Print ONLY non-sensitive booleans. Never print raw source.
    print("LIVE_WORKER_V58_MARKER="+str(result["v58_marker"]))
    print("LIVE_WORKER_LEGACY_LINK_FIELD="+str(result["legacy_single_link"]))
    print("LIVE_WORKER_TWO_LINK_FIELD="+str(result["multiple_links_field"]))
    print("LIVE_WORKER_TIER_FIELD="+str(result["tiers_field"]))
    if not (result["multiple_links_field"] and result["tiers_field"]):
        print("V59_TWO_LINK_CONTRACT=NOT_ESTABLISHED")
        return 1
    print("V59_TWO_LINK_CONTRACT=FIELDS_PRESENT_UI_STILL_UNVERIFIED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
