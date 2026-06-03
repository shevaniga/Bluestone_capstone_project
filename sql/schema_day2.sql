PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

DROP TABLE IF EXISTS fact_portfolio;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_sip_industry;
DROP TABLE IF EXISTS fact_category_inflows;
DROP TABLE IF EXISTS fact_folio_count;
DROP TABLE IF EXISTS fact_benchmark;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

CREATE TABLE dim_fund (
    amfi_code            TEXT    PRIMARY KEY,
    scheme_name          TEXT    NOT NULL,
    fund_house           TEXT    NOT NULL,
    category             TEXT,
    sub_category         TEXT,
    plan                 TEXT,
    benchmark            TEXT,
    fund_manager         TEXT,
    launch_date          DATE,
    expense_ratio_pct    REAL    CHECK (expense_ratio_pct BETWEEN 0.0 AND 3.0),
    exit_load_pct        REAL    DEFAULT 0.0,
    risk_category        TEXT,
    sebi_category_code   TEXT
);

CREATE TABLE dim_date (
    date_id      TEXT    PRIMARY KEY,
    full_date    DATE    NOT NULL,
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    quarter      INTEGER NOT NULL,
    month_name   TEXT    NOT NULL,
    day_of_week  TEXT    NOT NULL,
    is_weekday   INTEGER NOT NULL CHECK (is_weekday IN (0, 1)),
    is_month_end INTEGER NOT NULL CHECK (is_month_end IN (0, 1))
);

CREATE TABLE fact_nav (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code        TEXT    NOT NULL REFERENCES dim_fund(amfi_code),
    nav_date         TEXT    NOT NULL,
    nav              REAL    NOT NULL CHECK (nav > 0),
    daily_return_pct REAL,
    UNIQUE (amfi_code, nav_date)
);

CREATE TABLE fact_transactions (
    tx_id              TEXT    PRIMARY KEY,
    investor_id        TEXT    NOT NULL,
    amfi_code          TEXT    NOT NULL REFERENCES dim_fund(amfi_code),
    transaction_date   TEXT    NOT NULL,
    transaction_type   TEXT    NOT NULL CHECK (transaction_type IN ('SIP', 'Lumpsum', 'Redemption')),
    amount_inr         REAL    NOT NULL CHECK (amount_inr > 0),
    state              TEXT,
    city               TEXT,
    city_tier          TEXT    CHECK (city_tier IN ('T30', 'B30')),
    age_group          TEXT,
    gender             TEXT,
    annual_income_lakh REAL,
    payment_mode       TEXT,
    kyc_status         TEXT    CHECK (kyc_status IN ('Verified', 'Pending'))
);

CREATE TABLE fact_performance (
    amfi_code          TEXT    PRIMARY KEY REFERENCES dim_fund(amfi_code),
    as_of_date         TEXT    NOT NULL,
    return_1yr_pct     REAL,
    return_3yr_pct     REAL,
    return_5yr_pct     REAL,
    benchmark_3yr_pct  REAL,
    alpha              REAL,
    beta               REAL,
    sharpe_ratio       REAL,
    sortino_ratio      REAL,
    std_dev_ann_pct    REAL,
    max_drawdown_pct   REAL    CHECK (max_drawdown_pct <= 0),
    aum_crore          REAL,
    expense_ratio_pct  REAL,
    morningstar_rating INTEGER CHECK (morningstar_rating BETWEEN 1 AND 5)
);

CREATE TABLE fact_aum (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_house     TEXT    NOT NULL,
    report_date    TEXT    NOT NULL,
    aum_lakh_crore REAL,
    aum_crore      REAL    CHECK (aum_crore >= 0),
    num_schemes    INTEGER,
    UNIQUE (fund_house, report_date)
);

CREATE TABLE fact_sip_industry (
    month                     TEXT PRIMARY KEY,
    sip_inflow_crore          REAL,
    active_sip_accounts_crore REAL,
    new_sip_accounts_lakh     REAL,
    sip_aum_lakh_crore        REAL,
    yoy_growth_pct            REAL
);

CREATE TABLE fact_category_inflows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month         TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    net_inflow_cr REAL,
    UNIQUE (month, category)
);

CREATE TABLE fact_folio_count (
    month            TEXT PRIMARY KEY,
    total_folios_cr  REAL,
    equity_folios_cr REAL,
    debt_folios_cr   REAL,
    hybrid_folios_cr REAL
);

CREATE TABLE fact_portfolio (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code         TEXT    NOT NULL REFERENCES dim_fund(amfi_code),
    portfolio_date    TEXT    NOT NULL,
    stock_symbol      TEXT    NOT NULL,
    stock_name        TEXT,
    sector            TEXT,
    weight_pct        REAL    CHECK (weight_pct > 0 AND weight_pct <= 100),
    market_value_cr   REAL,
    current_price_inr REAL,
    UNIQUE (amfi_code, portfolio_date, stock_symbol)
);

CREATE TABLE fact_benchmark (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name       TEXT    NOT NULL,
    price_date       TEXT    NOT NULL,
    close_value      REAL    NOT NULL CHECK (close_value > 0),
    daily_return_pct REAL,
    UNIQUE (index_name, price_date)
);

CREATE INDEX IF NOT EXISTS idx_nav_code_date    ON fact_nav(amfi_code, nav_date);
CREATE INDEX IF NOT EXISTS idx_nav_date         ON fact_nav(nav_date);
CREATE INDEX IF NOT EXISTS idx_txn_investor     ON fact_transactions(investor_id);
CREATE INDEX IF NOT EXISTS idx_txn_code_date    ON fact_transactions(amfi_code, transaction_date);
CREATE INDEX IF NOT EXISTS idx_txn_state        ON fact_transactions(state);
CREATE INDEX IF NOT EXISTS idx_portfolio_code   ON fact_portfolio(amfi_code, portfolio_date);
CREATE INDEX IF NOT EXISTS idx_bench_name_date  ON fact_benchmark(index_name, price_date);
CREATE INDEX IF NOT EXISTS idx_perf_amfi        ON fact_performance(amfi_code);

CREATE VIEW IF NOT EXISTS v_latest_nav AS
SELECT
    n.amfi_code,
    f.scheme_name,
    f.fund_house,
    f.category,
    f.risk_category,
    n.nav_date,
    n.nav
FROM fact_nav n
JOIN dim_fund f ON f.amfi_code = n.amfi_code
WHERE n.nav_date = (
    SELECT MAX(nav_date) FROM fact_nav n2 WHERE n2.amfi_code = n.amfi_code
);

CREATE VIEW IF NOT EXISTS v_fund_scorecard AS
SELECT
    p.amfi_code,
    f.scheme_name,
    f.fund_house,
    f.category,
    f.risk_category,
    p.return_1yr_pct,
    p.return_3yr_pct,
    p.sharpe_ratio,
    p.alpha,
    p.max_drawdown_pct,
    p.aum_crore,
    p.expense_ratio_pct
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code;

CREATE VIEW IF NOT EXISTS v_monthly_sip_trend AS
SELECT
    month,
    sip_inflow_crore,
    active_sip_accounts_crore,
    sip_aum_lakh_crore,
    yoy_growth_pct,
    SUM(sip_inflow_crore) OVER (ORDER BY month ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS rolling_12m_inflow_cr
FROM fact_sip_industry
ORDER BY month;
