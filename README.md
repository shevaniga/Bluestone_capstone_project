# Bluestock Mutual Fund Analytics Platform
**Bluestock Fintech Capstone Project — June 2026**

> End-to-end data engineering, ETL pipeline, risk analytics and interactive dashboard for Indian Mutual Funds.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/shevaniga/Bluestone_capstone_project
cd Bluestone_capstone_project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place your 10 CSV files in data/raw/

# 4. Run the full pipeline
python scripts/run_pipeline.py

# 5. Launch the Streamlit dashboard
streamlit run dashboard/streamlit_app.py

# 6. Open Jupyter notebooks
jupyter notebook notebooks/
```

---

## Project Structure

```
bluestock_mf_capstone/
├── data/
│   ├── raw/
│   ├── processed/
│   └── db/
├── notebooks/
│   ├── 01_data_ingestion.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_eda_analysis.ipynb
│   ├── 04_performance_analytics.ipynb
│   └── 05_advanced_analytics.ipynb
├── scripts/
│   ├── run_pipeline.py
│   ├── etl_pipeline.py
│   ├── live_nav_fetch.py
│   ├── data_cleaning.py
│   ├── compute_metrics.py
│   ├── recommender.py
├── sql/
│   ├── schema.sql
│   └── queries.sql
│   └── queries_day2.sql
│   └── schema_day2.sql
├── dashboard/
│   ├── streamlit_app.py
│   ├── powerbi_dashboard.pdf
│   └── bluestock_mf_dashboard.pbix
├── reports/
│   ├── Final_Report.pdf
│   ├── Bluestock_MF_Presentation.pptx
│   └── charts/
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Datasets

Place all CSV files in `data/raw/` before running the pipeline.

| File | Rows | Description |
|------|------|-------------|
| 01_fund_master.csv | 40 | AMFI scheme master — codes, categories, risk grades |
| 02_nav_history.csv | ~46,000 | Daily NAV for all 40 schemes (Jan 2022 – May 2026) |
| 03_aum_by_fund_house.csv | ~90 | Quarterly AUM for 10 fund houses |
| 04_monthly_sip_inflows.csv | 48 | Monthly SIP inflows and account data |
| 05_category_inflows.csv | ~144 | Net inflows by fund category |
| 06_industry_folio_count.csv | 21 | Total folios by equity/debt/hybrid |
| 07_scheme_performance.csv | 40 | Sharpe, Beta, Alpha, Drawdown per scheme |
| 08_investor_transactions.csv | ~32,000 | SIP + Lumpsum + Redemption transactions |
| 09_portfolio_holdings.csv | ~320 | Stock-level holdings per fund |
| 10_benchmark_indices.csv | ~8,000 | Nifty 50, Nifty 100, BSE SmallCap daily values |

---

## Key Formulas

```python
CAGR       = (nav_end / nav_start) ** (252 / n_trading_days) - 1
Sharpe     = (mean_daily_return - Rf_daily) / std_daily * sqrt(252)   # Rf = 6.5%
Sortino    = (mean_daily_return - Rf_daily) / downside_std * sqrt(252)
Beta       = cov(fund_returns, bench_returns) / var(bench_returns)
Alpha      = OLS_intercept * 252
Max_DD     = min(nav / cummax(nav) - 1)
VaR_95     = np.percentile(daily_returns, 5)
CVaR_95    = mean(daily_returns[daily_returns <= VaR_95])
HHI        = sum(sector_weight_i ** 2)
```

---

## Bonus Challenges

| Bonus | Script | Description |
|-------|--------|-------------|
| B2 | dashboard/streamlit_app.py | 4-page Streamlit web dashboard |


---

## Tech Stack

Python 3.10+ · Pandas · NumPy · SciPy · Matplotlib · Seaborn · Plotly · SQLite · SQLAlchemy · Streamlit · Power BI · Jupyter · Git

---

## Common Mistakes Avoided

| Mistake | Fix |
|---------|-----|
| Hard-coded file paths | `pathlib.Path` throughout |
| Calendar-day CAGR | `252 / n_trading_days` |
| Weekend NAV gaps | `ffill()` after MultiIndex reindex |
| AUM unit confusion | `aum_lakh_crore` vs `aum_crore` labelled |
| `.db` in GitHub | `*.db` in `.gitignore` — share `schema.sql` |

---

_Bluestock Fintech · MF Analytics Capstone · June 2026 · Educational purposes only_
