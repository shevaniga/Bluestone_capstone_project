import pandas as pd
import numpy as np
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

PROJECT_DIR   = Path(__file__).resolve().parent.parent
RAW_DIR       = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
DB_PATH       = PROJECT_DIR / "data" / "db" / "bluestock_mf.db"

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


def load_raw(name: str, filename: str) -> pd.DataFrame | None:
    path = RAW_DIR / filename
    if not path.exists():
        log.warning(f"File not found: {path.name}")
        return None
    df = pd.read_csv(path, low_memory=False)
    for col in DATE_COLUMNS.get(name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    log.info(f"Loaded  '{name}' — {df.shape[0]:,} rows x {df.shape[1]} cols")
    return df


def clean_fund_master(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates(subset=["amfi_code"])
    df["amfi_code"]         = df["amfi_code"].astype(str).str.strip()
    df["fund_house"]        = df["fund_house"].str.strip().str.title()
    df["scheme_name"]       = df["scheme_name"].str.strip()
    df["category"]          = df["category"].str.strip().str.title()
    df["sub_category"]      = df["sub_category"].str.strip().str.title()
    df["plan"]              = df["plan"].str.strip().str.title()
    df["risk_category"]     = df["risk_category"].str.strip().str.title()
    df["expense_ratio_pct"] = pd.to_numeric(df["expense_ratio_pct"], errors="coerce")
    df["exit_load_pct"]     = pd.to_numeric(df["exit_load_pct"],     errors="coerce").fillna(0.0)

    valid_risk   = {"Low", "Moderate", "High", "Very High"}
    invalid_risk = df[~df["risk_category"].isin(valid_risk)]["risk_category"].unique()
    if len(invalid_risk):
        log.warning(f"  fund_master: unexpected risk_category values: {invalid_risk}")

    exp_out_of_range = df[(df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)]
    if len(exp_out_of_range):
        log.warning(f"  fund_master: {len(exp_out_of_range)} rows with expense_ratio_pct outside 0.1–2.5%")

    return df.reset_index(drop=True)


def clean_nav_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["amfi_code", "date", "nav"])
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df[df["nav"] > 0]
    df = df.drop_duplicates(subset=["amfi_code", "date"])
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    codes     = df["amfi_code"].unique()
    full_idx  = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    multi_idx = pd.MultiIndex.from_product([codes, full_idx], names=["amfi_code", "date"])

    df_filled = (
        df.set_index(["amfi_code", "date"])
        .reindex(multi_idx)["nav"]
        .groupby(level=0)
        .ffill()
        .reset_index()
    )
    df_filled = df_filled.dropna(subset=["nav"])

    filled_count = len(df_filled) - len(df)
    if filled_count > 0:
        log.info(f"  nav_history: forward-filled {filled_count:,} weekend/holiday rows")

    return df_filled


def clean_aum_by_fund_house(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["fund_house", "date"])
    df["fund_house"]    = df["fund_house"].str.strip().str.title()
    df["aum_lakh_crore"]= pd.to_numeric(df["aum_lakh_crore"], errors="coerce")
    df["aum_crore"]     = pd.to_numeric(df["aum_crore"],      errors="coerce")
    df["num_schemes"]   = pd.to_numeric(df["num_schemes"],    errors="coerce").astype("Int64")

    neg_aum = df[df["aum_crore"] < 0]
    if len(neg_aum):
        log.warning(f"  aum_by_fund_house: {len(neg_aum)} negative aum_crore rows dropped")
        df = df[df["aum_crore"] >= 0]

    return df.reset_index(drop=True)


def clean_monthly_sip_inflows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["month"])
    numeric_cols = [
        "sip_inflow_crore", "active_sip_accounts_crore",
        "new_sip_accounts_lakh", "sip_aum_lakh_crore", "yoy_growth_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("month").reset_index(drop=True)
    return df


def clean_category_inflows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    df = df.dropna(subset=["month", "category"])
    df["category"] = df["category"].str.strip().str.title()
    if "net_inflow_crore" in df.columns:
        df = df.rename(columns={"net_inflow_crore": "net_inflow_cr"})
    df["net_inflow_cr"] = pd.to_numeric(
        df["net_inflow_cr"],
        errors="coerce")
    if "gross_purchase_cr" in df.columns:
        df["gross_purchase_cr"] = pd.to_numeric(
            df["gross_purchase_cr"],
            errors="coerce"     )
    else:
        df["gross_purchase_cr"] = np.nan
    return df.reset_index(drop=True)


def clean_industry_folio_count(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["month"])
    num_cols = [c for c in df.columns if c != "month"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("month").reset_index(drop=True)


def clean_scheme_performance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.drop_duplicates(subset=["amfi_code"])
    numeric_cols = [
        "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
        "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio",
        "sortino_ratio", "std_dev_ann_pct", "max_drawdown_pct",
        "aum_crore", "expense_ratio_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    negative_sharpe = df[df["sharpe_ratio"] < 0]
    if len(negative_sharpe):
        log.warning(f"  scheme_performance: {len(negative_sharpe)} funds with negative Sharpe ratio (retained — valid)")

    exp_invalid = df[(df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)]
    if len(exp_invalid):
        log.warning(f"  scheme_performance: {len(exp_invalid)} rows with expense_ratio_pct outside 0.1–2.5%")

    return df.reset_index(drop=True)


def clean_investor_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["investor_id", "amfi_code", "transaction_date"])
    df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
    df = df[df["amount_inr"] > 0]

    valid_types  = {"SIP", "Lumpsum", "Redemption"}
    df["transaction_type"] = df["transaction_type"].str.strip().str.title()
    df["transaction_type"] = df["transaction_type"].replace({
        "Sip": "SIP", "Lump Sum": "Lumpsum", "Lump-Sum": "Lumpsum",
    })
    invalid_types = df[~df["transaction_type"].isin(valid_types)]
    if len(invalid_types):
        log.warning(f"  investor_transactions: {len(invalid_types)} rows with unrecognised transaction_type")

    valid_kyc = {"Verified", "Pending"}
    df["kyc_status"] = df["kyc_status"].str.strip().str.title()
    invalid_kyc = df[~df["kyc_status"].isin(valid_kyc)]
    if len(invalid_kyc):
        log.warning(f"  investor_transactions: {len(invalid_kyc)} rows with unrecognised kyc_status")

    df["city_tier"] = df["city_tier"].str.strip().str.upper()
    df = df.sort_values(["investor_id", "transaction_date"]).reset_index(drop=True)
    return df


def clean_portfolio_holdings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["amfi_code", "stock_symbol"])
    df["weight_pct"]        = pd.to_numeric(df["weight_pct"],        errors="coerce")
    df["market_value_cr"]   = pd.to_numeric(df["market_value_cr"],   errors="coerce")
    df["current_price_inr"] = pd.to_numeric(df["current_price_inr"], errors="coerce")
    df = df[df["weight_pct"] > 0]

    out_of_range = df[df["weight_pct"] > 100]
    if len(out_of_range):
        log.warning(f"  portfolio_holdings: {len(out_of_range)} rows with weight_pct > 100 — check data")

    df["sector"] = df["sector"].str.strip().str.title()
    return df.reset_index(drop=True)


def clean_benchmark_indices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["date", "index_name", "close_value"])
    df["close_value"] = pd.to_numeric(df["close_value"], errors="coerce")
    df = df[df["close_value"] > 0]
    df = df.drop_duplicates(subset=["index_name", "date"])

    df["index_name"] = df["index_name"].str.strip()
    df["daily_return_pct"] = (
        df.sort_values(["index_name", "date"])
        .groupby("index_name")["close_value"]
        .pct_change()
        .mul(100)
        .round(6)
    )
    return df.sort_values(["index_name", "date"]).reset_index(drop=True)


CLEANERS = {
    "fund_master"          : clean_fund_master,
    "nav_history"          : clean_nav_history,
    "aum_by_fund_house"    : clean_aum_by_fund_house,
    "monthly_sip_inflows"  : clean_monthly_sip_inflows,
    "category_inflows"     : clean_category_inflows,
    "industry_folio_count" : clean_industry_folio_count,
    "scheme_performance"   : clean_scheme_performance,
    "investor_transactions": clean_investor_transactions,
    "portfolio_holdings"   : clean_portfolio_holdings,
    "benchmark_indices"    : clean_benchmark_indices,
}


def cleaning_report(name: str, before: pd.DataFrame, after: pd.DataFrame) -> dict:
    return {
        "dataset"        : name,
        "rows_before"    : len(before),
        "rows_after"     : len(after),
        "rows_removed"   : len(before) - len(after),
        "nulls_before"   : int(before.isnull().sum().sum()),
        "nulls_after"    : int(after.isnull().sum().sum()),
        "dups_before"    : int(before.duplicated().sum()),
        "dups_after"     : int(after.duplicated().sum()),
    }


def load_to_sqlite(dataframes: dict):
    log.info(f"Loading to SQLite: {DB_PATH}")
    engine = create_engine(f"sqlite:///{DB_PATH}")

    TABLE_ORDER = [
        "fund_master", "nav_history", "aum_by_fund_house",
        "monthly_sip_inflows", "category_inflows", "industry_folio_count",
        "scheme_performance", "investor_transactions",
        "portfolio_holdings", "benchmark_indices",
    ]

    with engine.begin() as conn:
        for name in TABLE_ORDER:
            if name not in dataframes:
                log.warning(f"  Skipping '{name}' — not in dataframes")
                continue
            df = dataframes[name].copy()
            for col in df.select_dtypes(include=["datetime64[ns]"]).columns:
                df[col] = df[col].astype(str)
            df.to_sql(name, conn, if_exists="replace", index=False)
            log.info(f"  Loaded  '{name}' — {len(df):,} rows")

        _create_indexes(conn)

    log.info(f"SQLite database written: {DB_PATH}")


def _create_indexes(conn):
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_nav_code_date    ON nav_history(amfi_code, date);",
        "CREATE INDEX IF NOT EXISTS idx_nav_code         ON nav_history(amfi_code);",
        "CREATE INDEX IF NOT EXISTS idx_txn_investor     ON investor_transactions(investor_id);",
        "CREATE INDEX IF NOT EXISTS idx_txn_code_date    ON investor_transactions(amfi_code, transaction_date);",
        "CREATE INDEX IF NOT EXISTS idx_holdings_code    ON portfolio_holdings(amfi_code);",
        "CREATE INDEX IF NOT EXISTS idx_bench_name_date  ON benchmark_indices(index_name, date);",
        "CREATE INDEX IF NOT EXISTS idx_perf_amfi        ON scheme_performance(amfi_code);",
    ]
    for stmt in stmts:
        conn.execute(text(stmt))


def run_validation_queries(engine) -> pd.DataFrame:
    queries = {
        "Total NAV rows"               : "SELECT COUNT(*) AS count FROM nav_history",
        "Distinct funds in NAV"        : "SELECT COUNT(DISTINCT amfi_code) AS count FROM nav_history",
        "NAV date range"               : "SELECT MIN(date) AS start, MAX(date) AS end FROM nav_history",
        "Total investor transactions"  : "SELECT COUNT(*) AS count FROM investor_transactions",
        "Transaction type split"       : "SELECT transaction_type, COUNT(*) AS count FROM investor_transactions GROUP BY transaction_type",
        "Top 5 fund houses by AUM"     : "SELECT fund_house, ROUND(MAX(aum_crore),0) AS peak_aum_crore FROM aum_by_fund_house GROUP BY fund_house ORDER BY peak_aum_crore DESC LIMIT 5",
        "Schemes by category"          : "SELECT category, COUNT(*) AS schemes FROM fund_master GROUP BY category ORDER BY schemes DESC",
        "Negative Sharpe funds"        : "SELECT COUNT(*) AS count FROM scheme_performance WHERE sharpe_ratio < 0",
        "Expense ratio distribution"   : "SELECT ROUND(MIN(expense_ratio_pct),2) AS min, ROUND(AVG(expense_ratio_pct),2) AS avg, ROUND(MAX(expense_ratio_pct),2) AS max FROM fund_master",
        "Portfolio sector breakdown"   : "SELECT sector, COUNT(*) AS holdings, ROUND(AVG(weight_pct),2) AS avg_wt FROM portfolio_holdings GROUP BY sector ORDER BY avg_wt DESC LIMIT 10",
    }

    results = []
    with engine.connect() as conn:
        for label, query in queries.items():
            try:
                result = pd.read_sql_query(text(query), conn)
                print(f"\n  {label}:")
                print(result.to_string(index=False))
                results.append({"query": label, "status": "PASS", "rows": len(result)})
            except Exception as e:
                log.error(f"  Query failed — {label}: {e}")
                results.append({"query": label, "status": "FAIL", "rows": 0})

    return pd.DataFrame(results)


def save_cleaned_csvs(dataframes: dict):
    for name, df in dataframes.items():
        path = PROCESSED_DIR / f"clean_{name}.csv"
        df.to_csv(path, index=False)
        log.info(f"  Saved  clean_{name}.csv  ({len(df):,} rows)")


def save_cleaning_report(report_rows: list[dict]):
    df = pd.DataFrame(report_rows)
    path = PROCESSED_DIR / "cleaning_report.csv"
    df.to_csv(path, index=False)

    print(f"\n{'═'*65}")
    print("  CLEANING REPORT SUMMARY")
    print(f"{'═'*65}")
    print(df.to_string(index=False))
    print(f"{'═'*65}")

    log.info(f"  Cleaning report saved: {path.name}")


def main():
    log.info("=" * 60)
    log.info("  BLUESTOCK MF CAPSTONE — Day 2: Data Cleaning")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    raw_dfs     = {}
    clean_dfs   = {}
    report_rows = []

    log.info("\n[STEP 1] Loading raw datasets ...")
    for name, filename in DATASETS.items():
        df = load_raw(name, filename)
        if df is not None:
            raw_dfs[name] = df

    log.info(f"\n  {len(raw_dfs)}/{len(DATASETS)} datasets loaded.")

    if not raw_dfs:
        log.error("No datasets found. Place CSVs in data/raw/ and re-run.")
        return

    log.info("\n[STEP 2] Cleaning datasets ...")
    for name, cleaner in CLEANERS.items():
        if name not in raw_dfs:
            log.warning(f"  '{name}' not loaded — skipping cleaner")
            continue
        before       = raw_dfs[name]
        after        = cleaner(before)
        clean_dfs[name] = after
        report_rows.append(cleaning_report(name, before, after))
        log.info(f"  Cleaned '{name}': {len(before):,} → {len(after):,} rows")

    log.info("\n[STEP 3] Saving cleaned CSVs to data/processed/ ...")
    save_cleaned_csvs(clean_dfs)

    log.info("\n[STEP 4] Loading cleaned data into SQLite ...")
    load_to_sqlite(clean_dfs)

    log.info("\n[STEP 5] Running validation queries ...")
    print(f"\n{'─'*60}")
    print("  SQLite Validation")
    print(f"{'─'*60}")
    engine = create_engine(f"sqlite:///{DB_PATH}")
    query_results = run_validation_queries(engine)
    query_results.to_csv(PROCESSED_DIR / "sql_validation_results.csv", index=False)

    log.info("\n[STEP 6] Saving cleaning report ...")
    save_cleaning_report(report_rows)

    pass_count = query_results[query_results["status"] == "PASS"].shape[0]
    log.info("\n" + "=" * 60)
    log.info("  DAY 2 COMPLETE")
    log.info(f"  Datasets cleaned       : {len(clean_dfs)}")
    log.info(f"  SQL queries passed     : {pass_count}/{len(query_results)}")
    log.info(f"  SQLite DB              : {DB_PATH}")
    log.info(f"  Cleaned CSVs           : {PROCESSED_DIR}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
