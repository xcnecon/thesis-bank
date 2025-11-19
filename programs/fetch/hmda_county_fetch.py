#!/usr/bin/env python3
"""
hmda_refi_share_county.py

Zero-config script: builds county-level refinance share from HMDA for 2020–2021,
then saves hmda_refi_share_county_2020_2021.csv in the current directory.

Definition:
  Numerator: loan_purpose ∈ {31, 32} (refi, cash-out)
  Denominator: loan_purpose ∈ {1, 31, 32}

Filters:
  action_taken = 1
  Exclude open_end_line_of_credit = 1
  Exclude reverse_mortgage = 1
  Exclude business_or_commercial_purpose = 1
  Keep Single Family (1–4 Units) via derived_dwelling_category
  Keep first-lien only (lien_status = 1)
"""

import io, time
from typing import Iterable, List
import pandas as pd, requests

# Years and output
YEARS = [2020, 2021]
OUTPUT_CSV = "data/raw/HMDA.csv"

# API endpoint
DB_API_CSV = "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv"  # HMDA Data Browser API

# US state/territory postal abbreviations used by HMDA API
STATE_ABBR = [
    "AL","AK","AZ","AR","CA","CO","CT","DC","DE","FL","GA","HI","IA","ID","IL","IN","KS","KY","LA","MA",
    "MD","ME","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY","OH","OK","OR","PA","RI",
    "SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY","PR"
]

# Columns to pull; keep memory sane by reading in chunks
USECOLS = [
    "activity_year","state_code","county_code","census_tract","action_taken","loan_purpose",
    "open-end_line_of_credit","reverse_mortgage","business_or_commercial_purpose",
    "derived_dwelling_category","lien_status","occupancy_type","total_units",
]

DWELLING_OK = {
    "Single Family (1-4 Units):Site-Built",
    "Single Family (1-4 Units):Manufactured",
}

def iter_api(year: int, state: str) -> Iterable[pd.DataFrame]:
    """Stream filtered HMDA rows via API for a given year/state."""
    params = {
        "years": str(year),
        "states": state,
        "actions_taken": "1",
        "loan_purposes": "1,31,32",
        "lien_status": "1",
    }
    # Retry a few times in case the API is slow or transiently unavailable
    for attempt in range(3):
        try:
            r = requests.get(DB_API_CSV, params=params, stream=True, timeout=300)
            r.raise_for_status()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    # Stream to pandas to avoid loading entire file in memory
    r.raw.decode_content = True
    buf = r.raw
    for ch in pd.read_csv(
        buf,
        low_memory=False,
        chunksize=250_000,
        usecols=USECOLS,
        dtype={
            "state_code":"string","county_code":"string","census_tract":"string","action_taken":"Int64",
            "loan_purpose":"Int64","reverse_mortgage":"Int64",
            "business_or_commercial_purpose":"Int64","derived_dwelling_category":"string","lien_status":"Int64",
            "occupancy_type":"Int64","total_units":"string","activity_year":"Int64",
        },
    ):
        # Normalize HMDA header variations
        if "open-end_line_of_credit" in ch.columns and "open_end_line_of_credit" not in ch.columns:
            ch = ch.rename(columns={"open-end_line_of_credit": "open_end_line_of_credit"})
        yield ch
    r.close()

def filter_and_count(df: pd.DataFrame) -> pd.DataFrame:
    """Apply filters, aggregate to county-year, and compute refi share."""
    # Base filters
    df = df[df.action_taken == 1]
    # Optional exclusion flags (apply only if present)
    for col in ["open_end_line_of_credit", "reverse_mortgage", "business_or_commercial_purpose"]:
        if col in df.columns:
            df = df[df[col] != 1]
    if "derived_dwelling_category" in df.columns:
        df = df[df.derived_dwelling_category.isin(DWELLING_OK)]
    else:
        df = df[df.total_units.isin(["1","2","3","4"])]

    # First lien only
    if "lien_status" in df.columns:
        df = df[df.lien_status == 1]

    # Build numerator/denominator
    df = df[df.loan_purpose.isin([1, 31, 32])].copy()
    df["_denom"] = 1
    df["_num"] = df.loan_purpose.isin([31, 32]).astype("int8")

    # County FIPS
    df["state_fips"] = df.state_code.str.zfill(2)
    df["county_fips"] = df.county_code.str.zfill(3)
    df["fips5"] = df["state_fips"] + df["county_fips"]

    key = ["activity_year","fips5","state_fips","county_fips"]
    out = (
        df.groupby(key, as_index=False)[["_denom","_num"]]
        .sum()
        .rename(columns={"_denom":"orig_total","_num":"refi_total"})
    )
    out["refi_share"] = (out.refi_total / out.orig_total).where(out.orig_total > 0)
    out = out.rename(columns={"activity_year":"year"})
    return out

def process_year(year: int) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for st in STATE_ABBR:
        print(f"  {st}: fetching ...", flush=True)
        chunk_count = 0
        row_count = 0
        for ch in iter_api(year, st):
            chunk_count += 1
            row_count += len(ch)
            frames.append(filter_and_count(ch))
            if chunk_count % 5 == 0:
                print(f"  {st}: {row_count:,} rows so far ({chunk_count} chunks)", flush=True)
        print(f"  {st}: done, {row_count:,} rows", flush=True)
    yr = pd.concat(frames, ignore_index=True)
    return yr

def run():
    per_year = []
    for y in YEARS:
        print(f"Processing HMDA via API for {y} ...")
        per_year.append(process_year(y))
    df = pd.concat(per_year, ignore_index=True)

    # Final aggregation across chunks: ensure unique (year, fips5)
    agg = (
        df.groupby(["year", "fips5"], as_index=False)[["orig_total", "refi_total"]]
        .sum()
    )
    agg["refi_share"] = (agg["refi_total"] / agg["orig_total"]).where(agg["orig_total"] > 0)
    agg["state_fips"] = agg["fips5"].astype("string").str.slice(0, 2)
    agg["county_fips"] = agg["fips5"].astype("string").str.slice(2, 5)

    cols = ["year","fips5","state_fips","county_fips","orig_total","refi_total","refi_share"]
    agg = agg[cols].sort_values(["year","fips5"]).reset_index(drop=True)

    # Weighted average across 2020–2021 per fips5:
    # sum orig_total and refi_total, then recompute refi_share = sum(refi_total) / sum(orig_total)
    w = (
        agg.groupby("fips5", as_index=False)[["orig_total", "refi_total"]]
        .sum()
        .sort_values("fips5")
        .reset_index(drop=True)
    )
    w["refi_share"] = (w["refi_total"] / w["orig_total"]).where(w["orig_total"] > 0)

    # Save fips5 with aggregate totals and weighted refi_share
    w[["fips5", "orig_total", "refi_total", "refi_share"]].to_csv(OUTPUT_CSV, index=False)
    print(f"Saved: {OUTPUT_CSV} ({len(w):,} rows)")

if __name__ == "__main__":
    run()
