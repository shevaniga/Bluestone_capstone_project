import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

PROJECT_DIR   = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
CHARTS_DIR    = PROJECT_DIR / "reports" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

RF_ANNUAL  = 0.065
RF_DAILY   = RF_ANNUAL / 252
TRADING_DAYS = 252


def load_data():
    def read(name):
        p = PROCESSED_DIR / f"clean_{name}.csv"
        if not p.exists():
            p = PROJECT_DIR / "data" / "raw" / f"{name}.csv"
        return pd.read_csv(p, low_memory=False)

    nav    = read("nav_history")
    funds  = read("fund_master")
    bench  = read("benchmark_indices")
    perf   = read("scheme_performance")

    nav["date"]      = pd.to_datetime(nav["date"],  errors="coerce")
    nav["nav"]       = pd.to_numeric(nav["nav"],    errors="coerce")
    nav["amfi_code"] = nav["amfi_code"].astype(str)
    funds["amfi_code"] = funds["amfi_code"].astype(str)

    bench["date"]        = pd.to_datetime(bench["date"], errors="coerce")
    bench["close_value"] = pd.to_numeric(bench["close_value"], errors="coerce")

    nav = nav.merge(
        funds[["amfi_code","scheme_name","fund_house","category",
               "sub_category","risk_category","expense_ratio_pct"]],
        on="amfi_code", how="left"
    )
    return nav, funds, bench, perf


def compute_daily_returns(nav: pd.DataFrame) -> pd.DataFrame:
    nav = nav.sort_values(["amfi_code","date"])
    nav["daily_return"] = (nav.groupby("amfi_code")["nav"]
                           .pct_change())
    nav = nav.dropna(subset=["daily_return"])
    nav = nav[np.isfinite(nav["daily_return"])]
    nav = nav[nav["daily_return"].between(-0.5, 0.5)]
    log.info(f"Daily returns computed: {len(nav):,} rows")
    return nav


def compute_cagr(nav: pd.DataFrame, years: int) -> pd.Series:
    cutoff = nav["date"].max() - pd.DateOffset(years=years)
    results = {}
    for code, grp in nav.groupby("amfi_code"):
        grp = grp.sort_values("date")
        end_nav   = grp["nav"].iloc[-1]
        start_row = grp[grp["date"] >= cutoff]
        if len(start_row) < 20:
            results[code] = np.nan
            continue
        start_nav    = start_row["nav"].iloc[0]
        n_days       = len(start_row)
        n_years      = n_days / TRADING_DAYS
        results[code] = (end_nav / start_nav) ** (1 / n_years) - 1
    return pd.Series(results, name=f"cagr_{years}yr")


def compute_sharpe(returns: pd.DataFrame) -> pd.Series:
    def sharpe(r):
        excess = r - RF_DAILY
        if len(excess) < 20 or excess.std() == 0:
            return np.nan
        return (excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS)
    return returns.groupby("amfi_code")["daily_return"].apply(sharpe).rename("sharpe_ratio")


def compute_sortino(returns: pd.DataFrame) -> pd.Series:
    def sortino(r):
        excess    = r - RF_DAILY
        downside  = r[r < 0]
        if len(downside) < 5 or downside.std() == 0:
            return np.nan
        return (excess.mean() / downside.std()) * np.sqrt(TRADING_DAYS)
    return returns.groupby("amfi_code")["daily_return"].apply(sortino).rename("sortino_ratio")


def compute_alpha_beta(nav_returns: pd.DataFrame,
                       bench: pd.DataFrame) -> pd.DataFrame:
    nifty = (bench[bench["index_name"].str.contains("Nifty 100", case=False, na=False)]
             .sort_values("date")
             .set_index("date")["close_value"]
             .pct_change()
             .dropna()
             .rename("bench_return"))

    rows = []
    for code, grp in nav_returns.groupby("amfi_code"):
        fund_r  = grp.set_index("date")["daily_return"].dropna()
        aligned = pd.concat([fund_r, nifty], axis=1, join="inner").dropna()
        if len(aligned) < 60:
            rows.append({"amfi_code": code, "alpha": np.nan,
                         "beta": np.nan, "r_squared": np.nan, "tracking_error": np.nan})
            continue
        slope, intercept, r_val, _, _ = stats.linregress(
            aligned["bench_return"], aligned["daily_return"])
        alpha_ann    = intercept * TRADING_DAYS
        r_squared    = r_val ** 2
        track_err    = (aligned["daily_return"] - aligned["bench_return"]).std() * np.sqrt(TRADING_DAYS)
        rows.append({"amfi_code": code, "alpha": round(alpha_ann, 6),
                     "beta": round(slope, 4),
                     "r_squared": round(r_squared, 4),
                     "tracking_error": round(track_err, 6)})
    return pd.DataFrame(rows)


def compute_max_drawdown(nav: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code, grp in nav.groupby("amfi_code"):
        grp       = grp.sort_values("date").copy()
        roll_max  = grp["nav"].cummax()
        drawdown  = (grp["nav"] - roll_max) / roll_max
        max_dd    = drawdown.min()
        dd_end    = drawdown.idxmin()
        peak_idx  = grp.loc[:dd_end, "nav"].idxmax()
        rows.append({
            "amfi_code"    : code,
            "max_drawdown" : round(max_dd, 6),
            "dd_start_date": grp.loc[peak_idx, "date"].date() if pd.notna(peak_idx) else np.nan,
            "dd_end_date"  : grp.loc[dd_end,  "date"].date() if pd.notna(dd_end)  else np.nan,
            "dd_duration_days": (grp.loc[dd_end, "date"] - grp.loc[peak_idx, "date"]).days
                                if pd.notna(peak_idx) and pd.notna(dd_end) else np.nan,
        })
    return pd.DataFrame(rows)


def build_scorecard(metrics: pd.DataFrame) -> pd.DataFrame:
    df = metrics.copy()
    df["rank_3yr"]   = df["cagr_3yr"].rank(ascending=True,  na_option="bottom")
    df["rank_sharpe"]= df["sharpe_ratio"].rank(ascending=True,  na_option="bottom")
    df["rank_alpha"] = df["alpha"].rank(ascending=True,  na_option="bottom")
    df["rank_ter"]   = df["expense_ratio_pct"].rank(ascending=False, na_option="bottom")
    df["rank_dd"]    = df["max_drawdown"].rank(ascending=False, na_option="bottom")

    n = len(df)
    df["score"] = (
        0.30 * (df["rank_3yr"]    / n) +
        0.25 * (df["rank_sharpe"] / n) +
        0.20 * (df["rank_alpha"]  / n) +
        0.15 * (df["rank_ter"]    / n) +
        0.10 * (df["rank_dd"]     / n)
    ) * 100

    df["scorecard_rank"] = df["score"].rank(ascending=False).astype(int)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def main():
    log.info("=" * 60)
    log.info("  BLUESTOCK MF CAPSTONE — Day 4: Performance Analytics")
    log.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    nav, funds, bench, perf_src = load_data()

    log.info("\n[STEP 1] Computing daily returns ...")
    nav_r = compute_daily_returns(nav)
    nav_r.to_csv(PROCESSED_DIR / "returns_computed.csv", index=False)

    log.info("\n[STEP 2] Computing CAGR (1yr / 3yr / 5yr) ...")
    cagr_1 = compute_cagr(nav, 1)
    cagr_3 = compute_cagr(nav, 3)
    cagr_5 = compute_cagr(nav, 5)
    cagr_df = pd.concat([cagr_1, cagr_3, cagr_5], axis=1).reset_index().rename(columns={"index":"amfi_code"})
    cagr_df.to_csv(PROCESSED_DIR / "cagr_report.csv", index=False)

    log.info("\n[STEP 3] Computing Sharpe and Sortino ...")
    sharpe  = compute_sharpe(nav_r)
    sortino = compute_sortino(nav_r)

    log.info("\n[STEP 4] Computing Alpha and Beta (vs Nifty 100) ...")
    ab_df = compute_alpha_beta(nav_r, bench)
    ab_df.to_csv(PROCESSED_DIR / "alpha_beta.csv", index=False)

    log.info("\n[STEP 5] Computing Maximum Drawdown ...")
    dd_df = compute_max_drawdown(nav)
    dd_df.to_csv(PROCESSED_DIR / "max_drawdown.csv", index=False)

    log.info("\n[STEP 6] Building composite fund scorecard ...")
    metrics = (funds[["amfi_code","scheme_name","fund_house","category",
                       "sub_category","risk_category","expense_ratio_pct"]]
               .merge(cagr_df,           on="amfi_code", how="left")
               .merge(sharpe.reset_index(),  on="amfi_code", how="left")
               .merge(sortino.reset_index(), on="amfi_code", how="left")
               .merge(ab_df[["amfi_code","alpha","beta","r_squared","tracking_error"]], on="amfi_code", how="left")
               .merge(dd_df[["amfi_code","max_drawdown","dd_start_date","dd_end_date"]], on="amfi_code", how="left"))

    scorecard = build_scorecard(metrics)
    scorecard.to_csv(PROCESSED_DIR / "fund_scorecard.csv", index=False)

    log.info("\n" + "=" * 60)
    log.info("  TOP 10 FUNDS BY SCORECARD")
    log.info("=" * 60)
    cols = ["scorecard_rank","scheme_name","score","cagr_3yr","sharpe_ratio","alpha","max_drawdown"]
    top10 = scorecard[cols].head(10)
    top10["cagr_3yr"]     = (top10["cagr_3yr"]    * 100).round(2)
    top10["sharpe_ratio"] = top10["sharpe_ratio"].round(4)
    top10["alpha"]        = (top10["alpha"]        * 100).round(4)
    top10["max_drawdown"] = (top10["max_drawdown"] * 100).round(2)
    top10["score"]        = top10["score"].round(2)
    log.info("\n" + top10.to_string(index=False))

    log.info("\n[STEP 7] All metrics saved to data/processed/")
    for fname in ["returns_computed.csv","cagr_report.csv","alpha_beta.csv",
                  "max_drawdown.csv","fund_scorecard.csv"]:
        p = PROCESSED_DIR / fname
        if p.exists():
            df = pd.read_csv(p)
            log.info(f"  {fname:<30} {len(df):,} rows")

    log.info("\n" + "=" * 60)
    log.info("  DAY 4 COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
