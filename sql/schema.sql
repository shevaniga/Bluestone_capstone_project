-- ============================================================
-- schema.sql  —  Bluestock MF Capstone SQLite Database
-- ============================================================
-- Run:  sqlite3 data/db/bluestock_mf.db < sql/schema.sql
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ── 1. Fund Master ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fund_master (
    amfi_code        INTEGER PRIMARY KEY,
    scheme_name      TEXT    NOT NULL,
    fund_house       TEXT    NOT NULL,
    category         TEXT,
    sub_category     TEXT,
    risk_grade       TEXT,         -- Low / Moderate / High / Very High
    launch_date      DATE,
    benchmark        TEXT,
    exit_load_pct    REAL,
    lock_in_months   INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── 2. NAV History ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS nav_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code   INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    nav_date    DATE    NOT NULL,
    nav         REAL    NOT NULL CHECK (nav > 0),
    UNIQUE (amfi_code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_nav_code_date ON nav_history(amfi_code, nav_date);

-- ── 3. Scheme Details ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scheme_details (
    amfi_code         INTEGER PRIMARY KEY REFERENCES fund_master(amfi_code),
    plan_type         TEXT,       -- Direct / Regular
    option_type       TEXT,       -- Growth / IDCW
    min_sip_amount    REAL,
    min_lumpsum       REAL,
    fund_manager      TEXT,
    aum_cr            REAL,       -- AUM in ₹ Crore (scheme-level)
    updated_at        DATE
);

-- ── 4. AUM Data ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS aum_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    report_month    DATE    NOT NULL,   -- YYYY-MM-01 (first of month)
    aum_lakh_cr     REAL,               -- fund-house AUM in ₹ Lakh Crore
    aum_cr          REAL,               -- scheme-level AUM in ₹ Crore
    no_of_folios    INTEGER,
    UNIQUE (amfi_code, report_month)
);

-- ── 5. Portfolio Holdings ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    report_month    DATE    NOT NULL,
    isin            TEXT,
    stock_name      TEXT    NOT NULL,
    sector          TEXT,
    holding_pct     REAL    CHECK (holding_pct BETWEEN 0 AND 100),
    market_value_cr REAL,
    UNIQUE (amfi_code, report_month, isin)
);

-- ── 6. SIP Data ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sip_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    report_month    DATE    NOT NULL,
    sip_inflow_cr   REAL,
    sip_count       INTEGER,
    UNIQUE (amfi_code, report_month)
);

-- ── 7. Benchmark Returns ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS benchmark_returns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_name  TEXT    NOT NULL,
    return_date     DATE    NOT NULL,
    index_value     REAL,
    daily_return    REAL,
    UNIQUE (benchmark_name, return_date)
);

-- ── 8. Risk Metrics ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    as_of_date      DATE    NOT NULL,
    sharpe_ratio    REAL,
    beta            REAL,
    alpha           REAL,
    std_dev         REAL,
    sortino_ratio   REAL,
    max_drawdown    REAL,
    var_95          REAL,   -- Value at Risk at 95% confidence
    UNIQUE (amfi_code, as_of_date)
);

-- ── 9. Investor Profile ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_profile (
    investor_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    age_group       TEXT,
    risk_appetite   TEXT,
    investment_goal TEXT,
    preferred_category TEXT,
    sip_amount      REAL,
    tenure_years    INTEGER
);

-- ── 10. Expense Ratio ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expense_ratio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL REFERENCES fund_master(amfi_code),
    effective_date  DATE    NOT NULL,
    ter_pct         REAL    CHECK (ter_pct BETWEEN 0 AND 5),  -- Total Expense Ratio %
    plan_type       TEXT,
    UNIQUE (amfi_code, effective_date, plan_type)
);

-- ── Useful views ──────────────────────────────────────────────

CREATE VIEW IF NOT EXISTS v_latest_nav AS
SELECT
    nh.amfi_code,
    fm.scheme_name,
    fm.fund_house,
    fm.category,
    fm.risk_grade,
    nh.nav_date  AS latest_date,
    nh.nav       AS latest_nav
FROM nav_history nh
JOIN fund_master fm ON fm.amfi_code = nh.amfi_code
WHERE nh.nav_date = (
    SELECT MAX(nav_date) FROM nav_history n2
    WHERE n2.amfi_code = nh.amfi_code
);

CREATE VIEW IF NOT EXISTS v_nav_with_meta AS
SELECT
    nh.amfi_code,
    fm.scheme_name,
    fm.fund_house,
    fm.category,
    fm.sub_category,
    fm.risk_grade,
    nh.nav_date,
    nh.nav
FROM nav_history nh
JOIN fund_master fm ON fm.amfi_code = nh.amfi_code;

-- ── End of schema ─────────────────────────────────────────────
