import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_DIR   = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

RISK_MAP = {
    "low"      : ["Low"],
    "moderate" : ["Moderate"],
    "high"     : ["High", "Very High"],
}

def load_data():
    def read(name):
        for pattern in [f"clean_{name}.csv", f"{name}.csv"]:
            p = PROCESSED_DIR / pattern
            if p.exists():
                return pd.read_csv(p, low_memory=False)
        raw = PROJECT_DIR / "data" / "raw"
        for f in raw.iterdir():
            if name.replace("_","").lower() in f.stem.replace("_","").lower():
                return pd.read_csv(f, low_memory=False)
        return pd.DataFrame()

    perf  = read("scheme_performance")
    funds = read("fund_master")

    if perf.empty or funds.empty:
        return pd.DataFrame()

    perf["amfi_code"]  = perf["amfi_code"].astype(str)
    funds["amfi_code"] = funds["amfi_code"].astype(str)

    for col in ["sharpe_ratio","sortino_ratio","return_3yr_pct",
                "return_1yr_pct","alpha","max_drawdown_pct","expense_ratio_pct","aum_crore"]:
        if col in perf.columns:
            perf[col] = pd.to_numeric(perf[col], errors="coerce")

    merged = perf.merge(
        funds[["amfi_code","scheme_name","fund_house","category",
               "sub_category","plan","risk_category","expense_ratio_pct"]],
        on="amfi_code", how="left", suffixes=("","_fm")
    )

    if "risk_category" not in merged.columns or merged["risk_category"].isna().all():
        if "risk_category_fm" in merged.columns:
            merged["risk_category"] = merged["risk_category_fm"]

    return merged


def recommend(risk_appetite: str, top_n: int = 3) -> pd.DataFrame:
    risk_key = risk_appetite.strip().lower()
    if risk_key not in RISK_MAP:
        raise ValueError(f"risk_appetite must be one of: {list(RISK_MAP.keys())}")

    df = load_data()
    if df.empty:
        return pd.DataFrame({"error": ["Data not found — run Day 2 first"]})

    target_grades = RISK_MAP[risk_key]
    filtered = df[df["risk_category"].isin(target_grades)].copy()

    if filtered.empty:
        filtered = df.copy()

    filtered = filtered.dropna(subset=["sharpe_ratio"])
    filtered = filtered.sort_values("sharpe_ratio", ascending=False)

    cols = ["scheme_name","fund_house","category","risk_category",
            "sharpe_ratio","return_3yr_pct","expense_ratio_pct",
            "max_drawdown_pct","aum_crore"]
    avail = [c for c in cols if c in filtered.columns]
    result = filtered[avail].head(top_n).reset_index(drop=True)
    result.index = result.index + 1

    for col in ["sharpe_ratio"]:
        if col in result.columns:
            result[col] = result[col].round(4)
    for col in ["return_3yr_pct","expense_ratio_pct","max_drawdown_pct"]:
        if col in result.columns:
            result[col] = result[col].round(2)
    for col in ["aum_crore"]:
        if col in result.columns:
            result[col] = result[col].round(0)

    return result


def full_recommendation_report() -> pd.DataFrame:
    rows = []
    for appetite in ["low","moderate","high"]:
        recs = recommend(appetite, top_n=3)
        recs["risk_appetite_input"] = appetite.title()
        recs["rank_within_group"]   = recs.index
        rows.append(recs)
    return pd.concat(rows, ignore_index=True)


if __name__ == "__main__":
    print("=" * 60)
    print("  BLUESTOCK MF — Fund Recommender")
    print("=" * 60)

    for appetite in ["Low","Moderate","High"]:
        print(f"\n{'─'*55}")
        print(f"  Risk Appetite: {appetite}")
        print(f"{'─'*55}")
        result = recommend(appetite)
        if "error" in result.columns:
            print(result["error"].iloc[0])
        else:
            print(result.to_string())

    report = full_recommendation_report()
    out    = PROCESSED_DIR / "recommendation_report.csv"
    report.to_csv(out, index=False)
    print(f"\nFull report saved: {out}")
    print("=" * 60)
