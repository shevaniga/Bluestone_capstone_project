-- ============================================================
-- queries.sql  —  Bluestock MF Capstone Analytical Queries
-- ============================================================

-- ── Q1: Latest NAV for all schemes ───────────────────────────
SELECT * FROM v_latest_nav
ORDER BY fund_house, scheme_name;

-- ── Q2: Top 10 funds by 1-Year return ────────────────────────
WITH nav_1yr AS (
    SELECT
        amfi_code,
        MAX(CASE WHEN nav_date = (SELECT MAX(nav_date) FROM nav_history) THEN nav END) AS nav_today,
        MAX(CASE WHEN nav_date <= DATE((SELECT MAX(nav_date) FROM nav_history), '-1 year')
             THEN nav END) AS nav_1yr_ago
    FROM nav_history
    GROUP BY amfi_code
)
SELECT
    fm.scheme_name,
    fm.fund_house,
    fm.category,
    ROUND((n.nav_today / n.nav_1yr_ago - 1) * 100, 2) AS return_1yr_pct
FROM nav_1yr n
JOIN fund_master fm ON fm.amfi_code = n.amfi_code
WHERE n.nav_1yr_ago IS NOT NULL
ORDER BY return_1yr_pct DESC
LIMIT 10;

-- ── Q3: Fund-house AUM breakdown ─────────────────────────────
SELECT
    fm.fund_house,
    COUNT(DISTINCT fm.amfi_code)     AS num_schemes,
    ROUND(SUM(sd.aum_cr), 2)         AS total_aum_cr,
    ROUND(AVG(er.ter_pct), 4)        AS avg_ter_pct
FROM fund_master fm
LEFT JOIN scheme_details sd ON sd.amfi_code = fm.amfi_code
LEFT JOIN expense_ratio  er ON er.amfi_code = fm.amfi_code
GROUP BY fm.fund_house
ORDER BY total_aum_cr DESC;

-- ── Q4: Risk-adjusted performance (Sharpe) ───────────────────
SELECT
    fm.scheme_name,
    fm.fund_house,
    fm.category,
    rm.sharpe_ratio,
    rm.beta,
    rm.alpha,
    rm.max_drawdown
FROM risk_metrics rm
JOIN fund_master fm ON fm.amfi_code = rm.amfi_code
WHERE rm.as_of_date = (SELECT MAX(as_of_date) FROM risk_metrics)
ORDER BY rm.sharpe_ratio DESC
LIMIT 20;

-- ── Q5: Category-wise average returns ────────────────────────
WITH returns AS (
    SELECT
        amfi_code,
        MAX(nav) AS nav_max,
        MIN(nav) AS nav_min,
        (MAX(CASE WHEN nav_date = (SELECT MAX(nav_date) FROM nav_history) THEN nav END)
         / MAX(CASE WHEN nav_date <= DATE((SELECT MAX(nav_date) FROM nav_history), '-3 year')
              THEN nav END) - 1) * 100 AS return_3yr_pct
    FROM nav_history
    GROUP BY amfi_code
)
SELECT
    fm.category,
    COUNT(*)                                  AS num_funds,
    ROUND(AVG(r.return_3yr_pct), 2)           AS avg_3yr_return_pct,
    ROUND(MAX(r.return_3yr_pct), 2)           AS best_3yr_return_pct,
    ROUND(MIN(r.return_3yr_pct), 2)           AS worst_3yr_return_pct
FROM returns r
JOIN fund_master fm ON fm.amfi_code = r.amfi_code
WHERE r.return_3yr_pct IS NOT NULL
GROUP BY fm.category
ORDER BY avg_3yr_return_pct DESC;

-- ── Q6: Funds with NAV history gaps > 5 days ─────────────────
WITH ordered AS (
    SELECT
        amfi_code,
        nav_date,
        LAG(nav_date) OVER (PARTITION BY amfi_code ORDER BY nav_date) AS prev_date
    FROM nav_history
),
gaps AS (
    SELECT
        amfi_code,
        nav_date,
        prev_date,
        JULIANDAY(nav_date) - JULIANDAY(prev_date) AS gap_days
    FROM ordered
    WHERE prev_date IS NOT NULL
)
SELECT
    fm.scheme_name,
    g.amfi_code,
    g.prev_date,
    g.nav_date,
    CAST(g.gap_days AS INTEGER) AS gap_days
FROM gaps g
JOIN fund_master fm ON fm.amfi_code = g.amfi_code
WHERE g.gap_days > 5
ORDER BY g.gap_days DESC
LIMIT 20;

-- ── Q7: Monthly SIP inflow trend ─────────────────────────────
SELECT
    strftime('%Y-%m', report_month) AS month,
    ROUND(SUM(sip_inflow_cr), 2)    AS total_sip_inflow_cr,
    SUM(sip_count)                  AS total_sip_count
FROM sip_data
GROUP BY month
ORDER BY month DESC
LIMIT 24;

-- ── Q8: Top holdings across all large-cap funds ──────────────
SELECT
    ph.stock_name,
    ph.sector,
    COUNT(DISTINCT ph.amfi_code)          AS num_funds_holding,
    ROUND(AVG(ph.holding_pct), 2)         AS avg_holding_pct,
    ROUND(SUM(ph.market_value_cr), 2)     AS total_market_value_cr
FROM portfolio_holdings ph
JOIN fund_master fm ON fm.amfi_code = ph.amfi_code
WHERE ph.report_month = (SELECT MAX(report_month) FROM portfolio_holdings)
GROUP BY ph.stock_name, ph.sector
ORDER BY num_funds_holding DESC, avg_holding_pct DESC
LIMIT 20;
