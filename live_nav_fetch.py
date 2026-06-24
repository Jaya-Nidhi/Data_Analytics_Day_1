"""
live_nav_fetch.py
------------------
Day 1: Fetch live NAV history from the mfapi.in public API and save it
as raw CSVs in data/raw/.

Covers:
- HDFC Top 100 Direct (scheme code 125497)
- 5 key schemes: SBI Bluechip, ICICI Bluechip, Nippon Large Cap,
  Axis Bluechip, Kotak Bluechip

IMPORTANT — AMFI codes can be reassigned over time (a scheme can close,
merge, or be renamed and its old code reused for something else). This
script does NOT blindly trust the code -> name mapping below: after every
fetch it checks the scheme_name actually returned by the API against the
expected name and prints a clear WARNING if they don't match, so you catch
stale/incorrect codes immediately instead of silently saving the wrong
fund's data.

Usage:
    python live_nav_fetch.py
    python live_nav_fetch.py --output-dir data/raw
"""

import argparse
import os
import time

import pandas as pd
import requests

BASE_URL = "https://api.mfapi.in/mf/{code}"

# scheme_code -> (label used for filenames, expected name fragment to sanity-check against)
SCHEMES = {
    125497: ("hdfc_top_100_direct", "hdfc"),
    119551: ("sbi_bluechip", "sbi"),
    120503: ("icici_bluechip", "icici"),
    118632: ("nippon_large_cap", "nippon"),
    119092: ("axis_bluechip", "axis"),
    120841: ("kotak_bluechip", "kotak"),
}


def fetch_scheme(code: int, timeout: int = 15) -> dict:
    url = BASE_URL.format(code=code)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") not in (None, "SUCCESS"):
        raise ValueError(f"API returned non-success status for code {code}: {payload.get('status')}")
    return payload


def save_scheme_csv(code: int, label: str, payload: dict, output_dir: str) -> str:
    meta = payload.get("meta", {})
    rows = payload.get("data", [])

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)

    df["scheme_code"] = code
    df["scheme_name"] = meta.get("scheme_name")
    df["fund_house"] = meta.get("fund_house")
    df["scheme_category"] = meta.get("scheme_category")

    out_path = os.path.join(output_dir, f"nav_{label}_{code}.csv")
    df.to_csv(out_path, index=False)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Fetch live NAV from mfapi.in")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--sleep", type=float, default=0.5,
                         help="seconds to wait between API calls (be polite to the free API)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Fetching {len(SCHEMES)} schemes from mfapi.in ...\n")
    results = []

    for code, (label, expected_fragment) in SCHEMES.items():
        try:
            payload = fetch_scheme(code)
        except Exception as e:
            print(f"[{code}] FAILED to fetch: {e}")
            results.append({"scheme_code": code, "label": label, "status": "error", "detail": str(e)})
            time.sleep(args.sleep)
            continue

        meta = payload.get("meta", {})
        actual_name = (meta.get("scheme_name") or "").lower()
        actual_house = (meta.get("fund_house") or "").lower()
        n_rows = len(payload.get("data", []))

        match = expected_fragment in actual_name or expected_fragment in actual_house
        status = "ok" if match else "WARNING: name mismatch"

        out_path = save_scheme_csv(code, label, payload, args.output_dir)

        print(f"[{code}] {meta.get('scheme_name')} ({meta.get('fund_house')}) "
              f"- {n_rows} NAV records - saved to {out_path}")
        if not match:
            print(f"    >>> WARNING: expected a scheme matching '{expected_fragment}' "
                  f"but the API returned '{meta.get('scheme_name')}'. "
                  f"Verify the scheme code before using this data.")

        results.append({
            "scheme_code": code,
            "label": label,
            "status": status,
            "scheme_name": meta.get("scheme_name"),
            "fund_house": meta.get("fund_house"),
            "n_records": n_rows,
            "output_file": out_path,
        })

        time.sleep(args.sleep)

    summary_df = pd.DataFrame(results)
    summary_path = os.path.join(args.output_dir, "live_nav_fetch_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    print(f"\nFetch summary saved to {summary_path}")
    print(summary_df[["scheme_code", "scheme_name", "status", "n_records"]].to_string(index=False))


if __name__ == "__main__":
    main()