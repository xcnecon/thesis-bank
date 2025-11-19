#!/usr/bin/env python3

"""
acs_county_fetch.py
Pulls county-level ACS 5-year (2021) features for depositor sophistication proxies
and saves a clean CSV keyed by 5-digit county FIPS (state+county).

Outputs (columns):
  - fips (5-char), state_fips, county_fips, name (County, State)
  - median_hh_income
  - share_ba_plus
  - share_age_65plus
  - share_internet_sub

How to run:
  # 1) Install deps
  pip install pandas requests

  # 2) (Optional) export a Census API key
  #    Get a free key: https://api.census.gov/data/key_signup.html
  export CENSUS_API_KEY="YOUR_KEY"

  # 3) Run nationwide (default output is data/raw/ACS.csv):
  python acs_county_fetch.py

  #    Or restrict to your counties via a CSV with a column named "fips" (5-digit):
  python acs_county_fetch.py --filter-county-list county_list.csv --out data/raw/ACS_filtered.csv

Notes:
  - Uses *only* B tables to avoid S-table naming headaches.
  - Year defaults to 2021 (the 2017–2021 ACS 5-year). Change with --year if you must.
  - All FIPS fields are strings; leading zeros preserved.
"""

import argparse
import os
import time

import pandas as pd
import requests


# -----------------------------
# Configuration
# -----------------------------
DEFAULT_YEAR = 2021  # ACS 5-year vintage aligned with 2017–2021
BASE_URL_TMPL = "https://api.census.gov/data/{year}/acs/acs5"

# Variables we need (B tables for stability)
ACS_VARS = [
    # Income
    "B19013_001E",  # Median household income

    # Education (25+ with BA+)
    "B15003_001E",  # Total 25+
    "B15003_022E",  # Bachelor's
    "B15003_023E",  # Master's
    "B15003_024E",  # Professional school
    "B15003_025E",  # Doctorate

    # Age (population 65+ share)
    "B01001_001E",  # Total population
    "B01001_020E", "B01001_021E", "B01001_022E", "B01001_023E", "B01001_024E", "B01001_025E",  # Male 65+
    "B01001_044E", "B01001_045E", "B01001_046E", "B01001_047E", "B01001_048E", "B01001_049E",  # Female 65+

    # Internet subscription (households with any subscription)
    "B28002_001E",  # Households total
    "B28002_013E",  # Households w/o Internet subscription
]

# Lower 48 + DC + AK + HI + PR
STATE_FIPS = [
    "01","02","04","05","06","08","09","10","11","12","13","15","16","17","18","19",
    "20","21","22","23","24","25","26","27","28","29","30","31","32","33","34","35",
    "36","37","38","39","40","41","42","44","45","46","47","48","49","50","51","53",
    "54","55","56","72"
]


# -----------------------------
# Helpers
# -----------------------------
def _request_with_retries(url: str, params: dict, max_retries: int = 5, backoff: float = 1.0):
    """Simple retry wrapper for 429/5xx responses."""
    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 200:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff * (2 ** attempt))
            continue
        r.raise_for_status()
    r.raise_for_status()
    return r


def fetch_state_counties(year: int, state_fips: str, api_key: str = "") -> pd.DataFrame:
    """
    Fetch all counties for a given state FIPS from ACS 5-year and return as DataFrame.
    """
    base_url = BASE_URL_TMPL.format(year=year)
    params = {
        "get": ",".join(["NAME"] + ACS_VARS),
        "for": "county:*",
        "in": f"state:{state_fips}",
    }
    if api_key:
        params["key"] = api_key

    r = _request_with_retries(base_url, params)
    data = r.json()
    header = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=header)

    # Ensure string types for FIPS components
    df["state"] = df["state"].astype(str).str.zfill(2)
    df["county"] = df["county"].astype(str).str.zfill(3)

    # Cast numeric columns
    for v in ACS_VARS:
        df[v] = pd.to_numeric(df[v], errors="coerce")

    return df


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    From raw ACS columns, compute clean features and return tidy frame.
    """
    # Education BA+
    ba_plus = df["B15003_022E"] + df["B15003_023E"] + df["B15003_024E"] + df["B15003_025E"]
    share_ba_plus = ba_plus.div(df["B15003_001E"]).replace([float("inf")], pd.NA)

    # Age 65+
    age65_cols = [
        "B01001_020E","B01001_021E","B01001_022E","B01001_023E","B01001_024E","B01001_025E",
        "B01001_044E","B01001_045E","B01001_046E","B01001_047E","B01001_048E","B01001_049E"
    ]
    age65_plus = df[age65_cols].sum(axis=1)
    share_age_65plus = age65_plus.div(df["B01001_001E"]).replace([float("inf")], pd.NA)

    # Internet subscription share (1 - no-internet / households)
    share_internet_sub = 1.0 - df["B28002_013E"].div(df["B28002_001E"]).replace([float("inf")], pd.NA)

    out = pd.DataFrame({
        "state_fips": df["state"].astype(str).str.zfill(2),
        "county_fips": df["county"].astype(str).str.zfill(3),
        "fips": (df["state"].astype(str).str.zfill(2) + df["county"].astype(str).str.zfill(3)),
        "name": df["NAME"],
        "median_hh_income": df["B19013_001E"],
        "share_ba_plus": share_ba_plus,
        "share_age_65plus": share_age_65plus,
        "share_internet_sub": share_internet_sub,
    })
    return out


def main():
    ap = argparse.ArgumentParser(description="Fetch ACS 5-year county features for depositor sophistication proxies.")
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR, help="ACS year (default: 2021, i.e., 2017–2021 5-year).")
    ap.add_argument("--out", type=str, default=os.path.join("data", "raw", "ACS.csv"), help="Output CSV path.")
    args = ap.parse_args()

    api_key = os.environ.get("CENSUS_API_KEY", "").strip()

    # Fetch all states and concat
    frames = []
    for st in STATE_FIPS:
        df_state = fetch_state_counties(args.year, st, api_key=api_key)
        frames.append(df_state)
    raw = pd.concat(frames, ignore_index=True)

    features = compute_features(raw)

    # Sort and save
    features = features.sort_values(["state_fips", "county_fips"]).reset_index(drop=True)
    # Keep nice dtypes
    for col in ["median_hh_income", "share_ba_plus", "share_age_65plus", "share_internet_sub"]:
        features[col] = pd.to_numeric(features[col], errors="coerce")

    # Ensure output directory exists
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    features.to_csv(args.out, index=False)
    print(f"Saved {len(features):,} rows to {args.out}")


if __name__ == "__main__":
    main()
