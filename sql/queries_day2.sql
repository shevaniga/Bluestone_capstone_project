SELECT
    f.scheme_name,
    f.fund_house,
    f.category,
    ROUND(p.aum_crore, 2) AS aum_crore,
    ROUND(p.return_3yr_pct, 2) AS return_3yr_pct,
    ROUND(p.sharpe_ratio, 4) AS sharpe_ratio
FROM fact_performance p
JOIN dim_fund f
    ON f.amfi_code = p.amfi_code
ORDER BY p.aum_crore DESC
LIMIT 5;

SELECT
    SUBSTR(nav_date, 1, 7) AS month,
    ROUND(AVG(nav), 2) AS avg_nav,
    COUNT(DISTINCT amfi_code) AS num_funds
FROM fact_nav
GROUP BY month
ORDER BY month;

SELECT
    SUBSTR(month, 1, 4) AS year,
    ROUND(SUM(sip_inflow_crore), 2) AS total_sip_inflow_crore,
    ROUND(AVG(yoy_growth_pct), 2) AS avg_yoy_growth_pct
FROM fact_sip_industry
GROUP BY year
ORDER BY year;

SELECT
    state,
    COUNT(*) AS total_transactions,
    ROUND(SUM(amount_inr), 2) AS total_amount_inr,
    ROUND(AVG(amount_inr), 2) AS avg_amount_inr,
    city_tier
FROM fact_transactions
GROUP BY state, city_tier
ORDER BY total_amount_inr DESC;

SELECT
    f.scheme_name,
    f.fund_house,
    f.category,
    f.plan,
    ROUND(f.expense_ratio_pct, 4) AS expense_ratio_pct
FROM dim_fund f
WHERE f.expense_ratio_pct < 1.0
ORDER BY f.expense_ratio_pct ASC;

SELECT
    f.scheme_name,
    f.fund_house,
    f.risk_category,
    ROUND(p.sharpe_ratio, 4) AS sharpe_ratio,
    ROUND(p.sortino_ratio, 4) AS sortino_ratio,
    ROUND(p.alpha, 4) AS alpha,
    ROUND(p.beta, 4) AS beta,
    ROUND(p.max_drawdown_pct, 2) AS max_drawdown_pct
FROM fact_performance p
JOIN dim_fund f
    ON f.amfi_code = p.amfi_code
ORDER BY p.sharpe_ratio DESC;

SELECT
    SUBSTR(transaction_date, 1, 7) AS month,
    transaction_type,
    COUNT(*) AS num_transactions,
    ROUND(SUM(amount_inr), 2) AS total_amount_inr
FROM fact_transactions
GROUP BY month, transaction_type
ORDER BY month, transaction_type;

SELECT
    stock_name,
    sector,
    COUNT(DISTINCT amfi_code) AS num_funds_holding,
    ROUND(AVG(weight_pct), 2) AS avg_weight_pct,
    ROUND(SUM(market_value_cr), 2) AS total_market_value_cr
FROM fact_portfolio
GROUP BY stock_name, sector
ORDER BY num_funds_holding DESC, avg_weight_pct DESC
LIMIT 10;

SELECT
    index_name,
    MIN(close_value) AS min_value,
    MAX(close_value) AS max_value,
    ROUND(
        (MAX(close_value) - MIN(close_value))
        / MIN(close_value) * 100,
        2
    ) AS total_return_pct,
    COUNT(*) AS trading_days
FROM fact_benchmark
WHERE price_date >= DATE('now', '-3 years')
GROUP BY index_name
ORDER BY total_return_pct DESC;

SELECT
    age_group,
    gender,
    COUNT(DISTINCT investor_id) AS num_investors,
    COUNT(*) AS num_sip_transactions,
    ROUND(AVG(amount_inr), 2) AS avg_sip_amount_inr,
    ROUND(SUM(amount_inr), 2) AS total_invested_inr
FROM fact_transactions
WHERE transaction_type = 'SIP'
GROUP BY age_group, gender
ORDER BY age_group, gender;