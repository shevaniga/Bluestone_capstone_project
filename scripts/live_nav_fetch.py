import requests
import pandas as pd
import json
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR     = PROJECT_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SCHEMES = {
    125497: "HDFC_Top100_Direct",
    119551: "SBI_Bluechip_Direct",
    120503: "ICICI_Bluechip_Direct",
    118632: "Nippon_LargeCap_Direct",
    119092: "Axis_Bluechip_Direct",
    120841: "Kotak_Bluechip_Direct",
}

BASE_URL = "https://api.mfapi.in/mf"
TIMEOUT  = 15
DELAY    = 0.5


def fetch_nav(scheme_code: int, scheme_name: str) -> pd.DataFrame | None:
    url = f"{BASE_URL}/{scheme_code}"
    try:
        log.info(f"Fetching {scheme_name} (code: {scheme_code}) ...")
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()

        payload = response.json()

        if payload.get("status") != "SUCCESS":
            log.warning(f"  API returned non-SUCCESS for {scheme_name}: {payload.get('status')}")
            return None

        meta        = payload.get("meta", {})
        nav_records = payload.get("data", [])

        if not nav_records:
            log.warning(f"  No NAV records returned for {scheme_name}.")
            return None

        df = pd.DataFrame(nav_records)
        df["amfi_code"]       = scheme_code
        df["scheme_name"]     = meta.get("scheme_name", scheme_name)
        df["fund_house"]      = meta.get("fund_house", "")
        df["scheme_type"]     = meta.get("scheme_type", "")
        df["scheme_category"] = meta.get("scheme_category", "")

        df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", dayfirst=True)
        df["nav"]  = pd.to_numeric(df["nav"], errors="coerce")

        df = df.sort_values("date").reset_index(drop=True)

        null_nav = df["nav"].isna().sum()
        if null_nav:
            log.warning(f"  Dropped {null_nav} rows with unparseable NAV for {scheme_name}.")
            df = df.dropna(subset=["nav"])

        df = df[df["nav"] > 0]

        full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
        df = (
            df.set_index("date")
            .reindex(full_range)
            .assign(
                amfi_code       = scheme_code,
                scheme_name     = df["scheme_name"].iloc[0],
                fund_house      = df["fund_house"].iloc[0],
                scheme_type     = df["scheme_type"].iloc[0],
                scheme_category = df["scheme_category"].iloc[0],
            )
        )
        df["nav"] = df["nav"].ffill()
        df = df.dropna(subset=["nav"]).reset_index().rename(columns={"index": "date"})

        log.info(
            f"  {scheme_name}: {len(df):,} records | "
            f"{df['date'].min().date()} -> {df['date'].max().date()} | "
            f"Latest NAV: {df['nav'].iloc[-1]:.4f}"
        )
        return df

    except requests.exceptions.Timeout:
        log.error(f"  Timeout fetching {scheme_name} (code: {scheme_code})")
    except requests.exceptions.HTTPError as e:
        log.error(f"  HTTP error for {scheme_name}: {e}")
    except requests.exceptions.RequestException as e:
        log.error(f"  Network error for {scheme_name}: {e}")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        log.error(f"  Parse error for {scheme_name}: {e}")
    return None


def save_nav(df: pd.DataFrame, scheme_name: str) -> Path:
    out_path = RAW_DIR / f"nav_{scheme_name}.csv"
    df.to_csv(out_path, index=False)
    log.info(f"  Saved -> {out_path.relative_to(PROJECT_DIR)}")
    return out_path


def build_summary(results: dict) -> pd.DataFrame:
    rows = []
    for code, (name, df) in results.items():
        if df is not None:
            rows.append({
                "amfi_code"  : code,
                "scheme_name": name,
                "records"    : len(df),
                "start_date" : df["date"].min().date(),
                "end_date"   : df["date"].max().date(),
                "latest_nav" : round(df["nav"].iloc[-1], 4),
                "min_nav"    : round(df["nav"].min(),    4),
                "max_nav"    : round(df["nav"].max(),    4),
                "status"     : "SUCCESS",
            })
        else:
            rows.append({
                "amfi_code"  : code,
                "scheme_name": name,
                "status"     : "FAILED",
            })
    return pd.DataFrame(rows)


def main():
    log.info("=" * 60)
    log.info("  BLUESTOCK MF CAPSTONE — Live NAV Fetch")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    results = {}

    log.info("\n[STEP 1] Fetching NAV data from mfapi.in ...")
    for code, name in SCHEMES.items():
        df = fetch_nav(code, name)
        if df is not None:
            save_nav(df, name)
        results[code] = (name, df)
        time.sleep(DELAY)

    log.info("\n[STEP 2] Building combined master CSV ...")
    all_dfs = [df for _, (_, df) in results.items() if df is not None]
    if all_dfs:
        combined      = pd.concat(all_dfs, ignore_index=True)
        combined_path = RAW_DIR / "nav_all_schemes_live.csv"
        combined.to_csv(combined_path, index=False)
        log.info(f"  Combined CSV saved -> {combined_path.relative_to(PROJECT_DIR)}")
        log.info(f"  Total rows: {len(combined):,}")

    log.info("\n[STEP 3] Writing fetch summary ...")
    summary      = build_summary(results)
    summary_path = RAW_DIR / "nav_fetch_summary.csv"
    summary.to_csv(summary_path, index=False)

    success = summary[summary["status"] == "SUCCESS"].shape[0]

    log.info("\n" + "=" * 60)
    log.info("  FETCH SUMMARY")
    log.info("=" * 60)
    log.info("\n" + summary.to_string(index=False))
    log.info(f"\n  {success}/{len(SCHEMES)} schemes fetched successfully.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()