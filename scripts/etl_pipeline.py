import pandas as pd
import numpy as np
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

PROJECT_DIR   = Path(__file__).resolve().parent.parent

RAW_DIR       = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
DB_PATH       = PROJECT_DIR / "data" / "db" / "bluestock.db"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATASETS = {
    "fund_master"          : "01_fund_master.csv",
    "nav_history"          : "02_nav_history.csv",
    "aum_by_fund_house"    : "03_aum_by_fund_house.csv",
    "monthly_sip_inflows"  : "04_monthly_sip_inflows.csv",
    "category_inflows"     : "05_category_inflows.csv",
    "industry_folio_count" : "06_industry_folio_count.csv",
    "scheme_performance"   : "07_scheme_performance.csv",
    "investor_transactions": "08_investor_transactions.csv",
    "portfolio_holdings"   : "09_portfolio_holdings.csv",
    "benchmark_indices"    : "10_benchmark_indices.csv",
}

DATE_COLUMNS = {
    "fund_master"          : ["launch_date"],
    "nav_history"          : ["date"],
    "aum_by_fund_house"    : ["date"],
    "monthly_sip_inflows"  : ["month"],
    "category_inflows"     : ["month"],
    "industry_folio_count" : ["month"],
    "investor_transactions": ["transaction_date"],
    "portfolio_holdings"   : ["portfolio_date"],
    "benchmark_indices"    : ["date"],
}


def load_csv(name: str, filename: str) -> pd.DataFrame | None:
    path = RAW_DIR / filename
    if not path.exists():
        log.warning(f"File not found: {path}")
        return None
    try:
        df = pd.read_csv(path, low_memory=False)
        date_cols = DATE_COLUMNS.get(name, [])
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        log.info(f"Loaded '{name}' — {df.shape[0]:,} rows x {df.shape[1]} cols")
        return df
    except Exception as e:
        log.error(f"Could not load '{name}': {e}")
        return None


def clean_nav_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["amfi_code", "date", "nav"])
    df = df[df["nav"] > 0]
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    codes = df["amfi_code"].unique()
    idx = pd.MultiIndex.from_product([codes, full_range], names=["amfi_code", "date"])
    df = (
        df.set_index(["amfi_code", "date"])
        .reindex(idx)
        .groupby(level=0)["nav"]
        .ffill()
        .reset_index()
    )
    df = df.dropna(subset=["nav"])
    return df


def clean_fund_master(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset=["amfi_code"])
    df["expense_ratio_pct"] = pd.to_numeric(df["expense_ratio_pct"], errors="coerce")
    df["exit_load_pct"]     = pd.to_numeric(df["exit_load_pct"],     errors="coerce")
    df["min_sip_amount"]    = pd.to_numeric(df["min_sip_amount"],    errors="coerce")
    df["min_lumpsum_amount"]= pd.to_numeric(df["min_lumpsum_amount"],errors="coerce")
    return df


def clean_aum_by_fund_house(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["fund_house", "aum_crore"])
    df["aum_crore"]       = pd.to_numeric(df["aum_crore"],       errors="coerce")
    df["aum_lakh_crore"]  = pd.to_numeric(df["aum_lakh_crore"],  errors="coerce")
    df["num_schemes"]     = pd.to_numeric(df["num_schemes"],      errors="coerce")
    return df


def clean_monthly_sip_inflows(df: pd.DataFrame) -> pd.DataFrame:
    df["sip_inflow_crore"]          = pd.to_numeric(df["sip_inflow_crore"],          errors="coerce")
    df["active_sip_accounts_crore"] = pd.to_numeric(df["active_sip_accounts_crore"], errors="coerce")
    df["new_sip_accounts_lakh"]     = pd.to_numeric(df["new_sip_accounts_lakh"],     errors="coerce")
    df["sip_aum_lakh_crore"]        = pd.to_numeric(df["sip_aum_lakh_crore"],        errors="coerce")
    df["yoy_growth_pct"]            = pd.to_numeric(df["yoy_growth_pct"],            errors="coerce")
    return df


def clean_investor_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["investor_id", "amfi_code", "transaction_date"])
    df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
    df = df[df["amount_inr"] > 0]
    return df


def clean_scheme_performance(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
        "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio",
        "sortino_ratio", "std_dev_ann_pct", "max_drawdown_pct",
        "aum_crore", "expense_ratio_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_portfolio_holdings(df: pd.DataFrame) -> pd.DataFrame:
    df["weight_pct"]       = pd.to_numeric(df["weight_pct"],       errors="coerce")
    df["market_value_cr"]  = pd.to_numeric(df["market_value_cr"],  errors="coerce")
    df["current_price_inr"]= pd.to_numeric(df["current_price_inr"],errors="coerce")
    df = df[df["weight_pct"] > 0]
    return df


def clean_benchmark_indices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["date", "index_name", "close_value"])
    df["close_value"] = pd.to_numeric(df["close_value"], errors="coerce")
    df = df.sort_values(["index_name", "date"]).reset_index(drop=True)
    return df


CLEANERS = {
    "fund_master"          : clean_fund_master,
    "nav_history"          : clean_nav_history,
    "aum_by_fund_house"    : clean_aum_by_fund_house,
    "monthly_sip_inflows"  : clean_monthly_sip_inflows,
    "investor_transactions": clean_investor_transactions,
    "scheme_performance"   : clean_scheme_performance,
    "portfolio_holdings"   : clean_portfolio_holdings,
    "benchmark_indices"    : clean_benchmark_indices,
}


def profile_dataframe(name: str, df: pd.DataFrame) -> dict:
    sep = "─" * 60
    print(f"\n{'═'*60}")
    print(f"  DATASET: {name.upper()}")
    print(f"{'═'*60}")
    print(f"\nShape: {df.shape[0]:,} rows x {df.shape[1]} cols")

    print("\nData Types:")
    for col, dt in df.dtypes.items():
        print(f"  {col:<40} {str(dt)}")

    print("\nFirst 3 Rows:")
    print(df.head(3).to_string())

    null_counts = df.isnull().sum()
    null_pct    = (null_counts / len(df) * 100).round(2)
    null_df     = pd.DataFrame({"null_count": null_counts, "null_%": null_pct})
    null_df     = null_df[null_df["null_count"] > 0]

    if not null_df.empty:
        print("\nNull Values:")
        print(null_df.to_string())
    else:
        print("\nNo null values.")

    dup = df.duplicated().sum()
    print(f"\nDuplicate Rows: {dup:,}")

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        print(f"\nNumeric Summary:")
        print(df[num_cols].describe().round(4).to_string())

    anomalies = detect_anomalies(name, df)
    if anomalies:
        print("\nAnomalies:")
        for a in anomalies:
            print(f"  • {a}")
    else:
        print("\nNo anomalies detected.")

    print(sep)

    return {
        "name"        : name,
        "rows"        : df.shape[0],
        "cols"        : df.shape[1],
        "null_cols"   : int((null_counts > 0).sum()),
        "total_nulls" : int(null_counts.sum()),
        "dup_rows"    : int(dup),
        "anomalies"   : anomalies,
    }


def detect_anomalies(name: str, df: pd.DataFrame) -> list[str]:
    issues = []

    if df.duplicated().sum() > 0:
        issues.append(f"{df.duplicated().sum():,} duplicate rows")

    for col in df.columns:
        pct = df[col].isnull().mean() * 100
        if pct > 20:
            issues.append(f"'{col}' has {pct:.1f}% nulls")

    nav_col = next((c for c in df.columns if c.lower() == "nav"), None)
    if nav_col:
        nav = pd.to_numeric(df[nav_col], errors="coerce")
        neg = (nav <= 0).sum()
        if neg:
            issues.append(f"{neg:,} rows with NAV <= 0")
        extreme = (nav > 100_000).sum()
        if extreme:
            issues.append(f"{extreme:,} rows with NAV > 1,00,000 — verify units")

    for col in df.columns:
        if "date" in col.lower():
            try:
                parsed  = pd.to_datetime(df[col], errors="coerce")
                bad     = parsed.isna().sum()
                future  = (parsed > pd.Timestamp.now()).sum()
                if bad:
                    issues.append(f"'{col}': {bad:,} unparseable dates")
                if future:
                    issues.append(f"'{col}': {future:,} future-dated records")
            except Exception:
                pass

    for col in df.columns:
        if "aum" in col.lower():
            aum = pd.to_numeric(df[col], errors="coerce")
            neg = (aum < 0).sum()
            if neg:
                issues.append(f"'{col}': {neg:,} negative AUM values")

    return issues


def explore_fund_master(df: pd.DataFrame):
    print(f"\n{'═'*60}")
    print("  FUND MASTER EXPLORATION")
    print(f"{'═'*60}")

    for label, col in [
        ("Fund Houses",    "fund_house"),
        ("Categories",     "category"),
        ("Sub-Categories", "sub_category"),
        ("Risk Grades",    "risk_category"),
    ]:
        if col in df.columns:
            vals = df[col].dropna().unique()
            print(f"\n{label} ({len(vals)}):")
            for v in sorted(vals):
                print(f"  {str(v):<45} {(df[col] == v).sum():>5,} schemes")

    codes = pd.to_numeric(df["amfi_code"], errors="coerce").dropna()
    print(f"\nAMFI Code Range: {int(codes.min())} — {int(codes.max())}  |  Unique: {codes.nunique():,}")
    if len(codes) != codes.nunique():
        print(f"  WARNING: {len(codes) - codes.nunique():,} duplicate AMFI codes found!")


def validate_amfi_codes(fund_master: pd.DataFrame, nav_history: pd.DataFrame) -> dict:
    print(f"\n{'═'*60}")
    print("  AMFI CODE VALIDATION")
    print(f"{'═'*60}")

    fm_codes  = set(pd.to_numeric(fund_master["amfi_code"],  errors="coerce").dropna().astype(int))
    nav_codes = set(pd.to_numeric(nav_history["amfi_code"],  errors="coerce").dropna().astype(int))

    in_both       = fm_codes & nav_codes
    in_fm_not_nav = fm_codes - nav_codes
    in_nav_not_fm = nav_codes - fm_codes

    print(f"\n  Fund Master codes      : {len(fm_codes):,}")
    print(f"  NAV History codes      : {len(nav_codes):,}")
    print(f"  Matched                : {len(in_both):,}")
    print(f"  In FM, not in NAV      : {len(in_fm_not_nav):,}")
    print(f"  In NAV, not in FM      : {len(in_nav_not_fm):,}")

    if in_fm_not_nav:
        print(f"\n  FM codes missing from NAV (first 10): {sorted(in_fm_not_nav)[:10]}")

    coverage     = round(len(in_both) / len(fm_codes) * 100, 2) if fm_codes else 0
    quality_flag = "PASS" if coverage >= 90 else ("WARN" if coverage >= 70 else "FAIL")
    print(f"\n  Coverage: {coverage}%  |  Quality: {quality_flag}")

    return {
        "fm_codes"      : len(fm_codes),
        "nav_codes"     : len(nav_codes),
        "matched"       : len(in_both),
        "in_fm_not_nav" : len(in_fm_not_nav),
        "in_nav_not_fm" : len(in_nav_not_fm),
        "coverage_pct"  : coverage,
        "quality_flag"  : quality_flag,
        "missing_sample": sorted(in_fm_not_nav)[:20],
    }


def load_to_sqlite(dataframes: dict):
    log.info(f"\n[STEP] Loading to SQLite — {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    table_map = {
        "fund_master"          : "fund_master",
        "nav_history"          : "nav_history",
        "aum_by_fund_house"    : "aum_by_fund_house",
        "monthly_sip_inflows"  : "monthly_sip_inflows",
        "category_inflows"     : "category_inflows",
        "industry_folio_count" : "industry_folio_count",
        "scheme_performance"   : "scheme_performance",
        "investor_transactions": "investor_transactions",
        "portfolio_holdings"   : "portfolio_holdings",
        "benchmark_indices"    : "benchmark_indices",
    }

    for key, table in table_map.items():
        if key not in dataframes:
            log.warning(f"  Skipping '{table}' — not loaded")
            continue
        df = dataframes[key].copy()
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].astype(str)
        df.to_sql(table, conn, if_exists="replace", index=False)
        log.info(f"  Loaded '{table}' — {len(df):,} rows")

    _create_indexes(conn)
    _run_validation_queries(conn)
    conn.close()
    log.info(f"  SQLite saved to: {DB_PATH}")


def _create_indexes(conn: sqlite3.Connection):
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_nav_code_date   ON nav_history(amfi_code, date);",
        "CREATE INDEX IF NOT EXISTS idx_nav_code        ON nav_history(amfi_code);",
        "CREATE INDEX IF NOT EXISTS idx_txn_investor    ON investor_transactions(investor_id);",
        "CREATE INDEX IF NOT EXISTS idx_txn_code        ON investor_transactions(amfi_code);",
        "CREATE INDEX IF NOT EXISTS idx_txn_date        ON investor_transactions(transaction_date);",
        "CREATE INDEX IF NOT EXISTS idx_holdings_code   ON portfolio_holdings(amfi_code);",
        "CREATE INDEX IF NOT EXISTS idx_bench_name_date ON benchmark_indices(index_name, date);",
    ]
    for stmt in indexes:
        conn.execute(stmt)
    conn.commit()


def _run_validation_queries(conn: sqlite3.Connection):
    print(f"\n{'─'*60}")
    print("  SQLite Validation Queries")
    print(f"{'─'*60}")

    queries = {
        "Total NAV rows"          : "SELECT COUNT(*) FROM nav_history;",
        "Distinct funds in NAV"   : "SELECT COUNT(DISTINCT amfi_code) FROM nav_history;",
        "NAV date range"          : "SELECT MIN(date), MAX(date) FROM nav_history;",
        "Total transactions"      : "SELECT COUNT(*) FROM investor_transactions;",
        "Transaction types"       : "SELECT transaction_type, COUNT(*) FROM investor_transactions GROUP BY transaction_type;",
        "AUM by top 5 fund houses": "SELECT fund_house, ROUND(MAX(aum_crore),0) as peak_aum_crore FROM aum_by_fund_house GROUP BY fund_house ORDER BY peak_aum_crore DESC LIMIT 5;",
        "Schemes per category"    : "SELECT category, COUNT(*) as schemes FROM fund_master GROUP BY category ORDER BY schemes DESC;",
    }

    for label, query in queries.items():
        try:
            result = pd.read_sql_query(query, conn)
            print(f"\n  {label}:")
            print(result.to_string(index=False))
        except Exception as e:
            print(f"\n  {label}: ERROR — {e}")


def save_processed_csvs(dataframes: dict):
    for name, df in dataframes.items():
        out = PROCESSED_DIR / f"{name}_clean.csv"
        df.to_csv(out, index=False)
        log.info(f"  Saved cleaned CSV: {out.name}")


def write_quality_report(profiles: list[dict], validation: dict):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "generated_at"     : ts,
        "dataset_profiles" : profiles,
        "amfi_validation"  : validation,
    }

    json_path = PROCESSED_DIR / "data_quality_report.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    md_lines = [
        "# Data Quality Report",
        f"_Generated: {ts}_\n",
        "## Dataset Profiles",
        "| Dataset | Rows | Cols | Null Cols | Dup Rows | Anomalies |",
        "|---------|-----:|-----:|----------:|---------:|-----------|",
    ]
    for p in profiles:
        n = len(p.get("anomalies", []))
        flag = "HIGH" if n > 2 else ("MEDIUM" if n else "LOW")
        md_lines.append(
            f"| {p['name']} | {p['rows']:,} | {p['cols']} | "
            f"{p.get('null_cols',0)} | {p.get('dup_rows',0):,} | {flag} {n} |"
        )

    md_lines += [
        "\n## AMFI Code Validation",
        f"- **Fund Master codes:** {validation.get('fm_codes', 'N/A')}",
        f"- **NAV History codes:** {validation.get('nav_codes', 'N/A')}",
        f"- **Matched:** {validation.get('matched', 'N/A')}",
        f"- **Coverage:** {validation.get('coverage_pct', 'N/A')}%",
        f"- **Quality Flag:** {validation.get('quality_flag', 'N/A')}",
        "\n### FM codes missing from NAV (first 20)",
        str(validation.get("missing_sample", [])),
    ]

    md_path = PROCESSED_DIR / "data_quality_report.md"
    md_path.write_text("\n".join(md_lines))

    log.info(f"  Quality report → {json_path.name} + {md_path.name}")


def main():
    log.info("=" * 60)
    log.info("  BLUESTOCK MF CAPSTONE — ETL Pipeline")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    dataframes = {}
    profiles   = []

    log.info("\n[STEP 1] Loading datasets...")
    for name, filename in DATASETS.items():
        df = load_csv(name, filename)
        if df is not None:
            dataframes[name] = df

    loaded = len(dataframes)
    log.info(f"  {loaded}/{len(DATASETS)} datasets loaded.")

    if loaded == 0:
        log.error("No datasets found. Place CSV files in data/raw/ and re-run.")
        return

    log.info("\n[STEP 2] Cleaning datasets...")
    for name, cleaner in CLEANERS.items():
        if name in dataframes:
            before = len(dataframes[name])
            dataframes[name] = cleaner(dataframes[name])
            after  = len(dataframes[name])
            if before != after:
                log.info(f"  '{name}': {before:,} → {after:,} rows after cleaning")

    log.info("\n[STEP 3] Profiling datasets...")
    for name, df in dataframes.items():
        profiles.append(profile_dataframe(name, df))

    log.info("\n[STEP 4] Exploring fund_master...")
    if "fund_master" in dataframes:
        explore_fund_master(dataframes["fund_master"])

    validation = {}
    log.info("\n[STEP 5] Validating AMFI codes...")
    if "fund_master" in dataframes and "nav_history" in dataframes:
        validation = validate_amfi_codes(dataframes["fund_master"], dataframes["nav_history"])
    else:
        missing = [k for k in ("fund_master", "nav_history") if k not in dataframes]
        log.warning(f"  Skipped — missing: {missing}")

    log.info("\n[STEP 6] Loading to SQLite...")
    load_to_sqlite(dataframes)

    log.info("\n[STEP 7] Saving cleaned CSVs...")
    save_processed_csvs(dataframes)

    log.info("\n[STEP 8] Writing quality report...")
    write_quality_report(profiles, validation)

    total_rows  = sum(p["rows"]  for p in profiles)
    total_nulls = sum(p.get("total_nulls", 0) for p in profiles)

    log.info("\n" + "=" * 60)
    log.info("  ETL COMPLETE")
    log.info(f"  Datasets loaded    : {loaded}")
    log.info(f"  Total rows         : {total_rows:,}")
    log.info(f"  Total null values  : {total_nulls:,}")
    log.info(f"  AMFI coverage      : {validation.get('coverage_pct', 'N/A')}%")
    log.info(f"  SQLite DB          : {DB_PATH}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()