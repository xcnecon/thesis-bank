#!/usr/bin/env python3
"""
Build county-level “market participation” proxies from IRS SOI:
  share_dividend = N00600 / N1
  share_interest = N00300 / N1

Default: COUNTY 2021 (no-AGI) direct. Optional: ZIP 2021 (no-AGI) + HUD ZIP→County crosswalk.

Usage:
  pip install pandas requests
  # COUNTY (no crosswalk)
  python programs/irs_county_fetch.py --mode county --out data/processed/irs.csv
  # ZIP (needs HUD crosswalk CSV with ZIP, COUNTY, TOT_RATIO or RES_RATIO)
  python programs/irs_county_fetch.py --mode zip --crosswalk hud_zip_county.csv --out data/processed/irs.csv
"""
import argparse, io, os, sys, warnings
import pandas as pd, requests

IRS_COUNTY_2021 = "https://www.irs.gov/pub/irs-soi/21incyallnoagi.csv"
IRS_ZIP_2021    = "https://www.irs.gov/pub/irs-soi/21zpallnoagi.csv"

def _get(url):
    for _ in range(5):
        r = requests.get(url, timeout=60)
        if r.status_code == 200: return r.content
        if r.status_code in (429,500,502,503,504): continue
        r.raise_for_status()
    raise RuntimeError(f"Fetch failed: {url}")

def _find(df, names):
    lo = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lo: return lo[n.lower()]
    squash = {c.lower().replace(" ","").replace("_",""): c for c in df.columns}
    for n in names:
        k = n.lower().replace(" ","").replace("_","")
        if k in squash: return squash[k]
    return None

def _need(df, cols, ctx):
    miss = [c for c in cols if _find(df,[c]) is None]
    if miss: raise ValueError(f"Missing {miss} in {ctx}. Got: {list(df.columns)[:15]} ...")

def county_shares(df):
    _need(df, ["N1","N00300","N00600"], "IRS COUNTY 2021")
    N1  = pd.to_numeric(df[_find(df,["N1"])], errors="coerce")
    N3  = pd.to_numeric(df[_find(df,["N00300"])], errors="coerce")
    N6  = pd.to_numeric(df[_find(df,["N00600"])], errors="coerce")
    st  = _find(df,["STATEFIPS","STATE"]); ct = _find(df,["COUNTYFIPS","COUNTY"])
    if not st or not ct: raise ValueError("No state/county FIPS columns.")
    sf  = df[st].astype(str).str.zfill(2); cf = df[ct].astype(str).str.zfill(3)
    fips = sf + cf
    nm  = _find(df,["COUNTYNAME","COUNTY_NAME","NAME"])
    stab= _find(df,["STATEABBR","STABBR","STATE_NAME"])
    out = pd.DataFrame({
        "fips": fips, "state_fips": sf, "county_fips": cf,
        "county_name": df[nm] if nm else pd.NA,
        "state_abbr":  df[stab] if stab else pd.NA,
        "returns_total": N1,
        "share_dividend": (N6/N1).where(N1>0),
        "share_interest": (N3/N1).where(N1>0),
    })
    return out[out["county_fips"]!="000"].reset_index(drop=True)

def zip_to_county(df_zip, xwalk, ratio="TOT_RATIO"):
    _need(df_zip, ["ZIPCODE","N1","N00300","N00600"], "IRS ZIP 2021 no-AGI")
    _need(xwalk, ["ZIP","COUNTY",ratio], f"HUD ZIP→County crosswalk (ratio={ratio})")
    df_zip["_zip"]=df_zip[_find(df_zip,["ZIPCODE"])].astype(str).str.zfill(5)
    for col in ("N1","N00300","N00600"):
        df_zip[f"_{col}"]=pd.to_numeric(df_zip[_find(df_zip,[col])], errors="coerce").fillna(0.0)
    xwalk = xwalk.copy()
    xwalk["_zip"]=xwalk[_find(xwalk,["ZIP"])].astype(str).str.zfill(5)
    xwalk["_county"]=xwalk[_find(xwalk,["COUNTY"])].astype(str).str.zfill(5)
    rcol=_find(xwalk,[ratio]); xwalk[rcol]=xwalk[rcol].astype(float)
    m = df_zip.merge(xwalk[["_zip","_county",rcol]], on="_zip", how="inner")
    for col in ("_N1","_N00300","_N00600"):
        m[col+"_alloc"]=m[col]*m[rcol]
    g = m.groupby("_county",as_index=False)[["_N1_alloc","_N00300_alloc","_N00600_alloc"]].sum()
    g["fips"]=g["_county"]; g["state_fips"]=g["fips"].str[:2]; g["county_fips"]=g["fips"].str[2:]
    g.rename(columns={"_N1_alloc":"returns_total","_N00300_alloc":"interest","_N00600_alloc":"dividends"},inplace=True)
    g["share_dividend"]=(g["dividends"]/g["returns_total"]).where(g["returns_total"]>0)
    g["share_interest"]=(g["interest"]/g["returns_total"]).where(g["returns_total"]>0)
    return g[["fips","state_fips","county_fips","returns_total","share_dividend","share_interest"]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["county","zip"], default="county")
    ap.add_argument("--crosswalk", default="", help="HUD ZIP→County CSV (needed if --mode zip)")
    ap.add_argument("--ratio-column", default="TOT_RATIO", help="TOT_RATIO or RES_RATIO")
    ap.add_argument("--out", default="data/raw/irs.csv")
    args = ap.parse_args()
    warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
    # Ensure output directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if args.mode=="county":
        raw = pd.read_csv(io.BytesIO(_get(IRS_COUNTY_2021)), encoding="latin1")
        out = county_shares(raw)
    else:
        if not args.crosswalk: sys.exit("ERROR: --crosswalk required for --mode zip")
        raw = pd.read_csv(io.BytesIO(_get(IRS_ZIP_2021)), encoding="latin1")
        xw  = pd.read_csv(args.crosswalk, dtype=str)
        out = zip_to_county(raw, xw, ratio=args.ratio_column)

    out.to_csv(args.out, index=False)
    print(f"Saved {len(out):,} rows to {args.out}")

if __name__ == "__main__":
    main()
