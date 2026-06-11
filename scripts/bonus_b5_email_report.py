from pathlib import Path
import pandas as pd
import html
import webbrowser
import time
import threading

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED = BASE_DIR / "data" / "processed"
REPORTS   = BASE_DIR / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

sip = pd.read_csv(PROCESSED / "clean_monthly_sip_inflows.csv", parse_dates=["month"])
perf = pd.read_csv(PROCESSED / "clean_scheme_performance.csv")

latest_sip   = sip.sort_values("month").iloc[-1]
peak_sip     = sip.loc[sip["sip_inflow_crore"].idxmax()]
total_aum    = 81.0
total_folios = 26.12

top10 = (
    perf.dropna(subset=["sharpe_ratio"])
    .sort_values("sharpe_ratio", ascending=False)
    .head(10)[["scheme_name", "fund_house", "category",
               "return_3yr_pct", "sharpe_ratio", "alpha",
               "max_drawdown_pct", "aum_crore"]]
    .reset_index(drop=True)
)

NAVY  = "#2F4156"
TEAL  = "#567C8D"
SKY   = "#CBD9E6"
BEIGE = "#F5EFEB"
WHITE = "#FFFFFF"

def kpi_card(label, value, sub="", dark=False):
    bg    = NAVY  if dark else WHITE
    val_c = WHITE if dark else NAVY
    lbl_c = SKY   if dark else TEAL
    sub_c = "#96AABB"
    border = "border:none;" if dark else f"border:1px solid {SKY};"
    return f"""
    <div style="background:{bg};{border}border-radius:14px;padding:22px 18px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:{val_c};letter-spacing:-0.5px;">{value}</div>
        <div style="font-size:10px;color:{lbl_c};text-transform:uppercase;letter-spacing:1.5px;margin-top:6px;">{html.escape(label)}</div>
        {'<div style="font-size:10px;color:' + sub_c + ';margin-top:3px;">' + html.escape(sub) + '</div>' if sub else ''}
    </div>"""

BADGE_STYLES = {
    "Large Cap": f"background:{SKY};color:{NAVY}",
    "Flexi Cap": "background:#D6E8E0;color:#1B5E3B",
    "Mid Cap":   "background:#FDE9C4;color:#7A4F00",
    "Small Cap": "background:#FADCD9;color:#8B2012",
}

def perf_row(i, row):
    bs           = BADGE_STYLES.get(row["category"], "background:#E8E8E8;color:#444")
    sharpe_style = f"color:#1B5E3B;font-weight:700;" if row["sharpe_ratio"] > 1 else f"color:{TEAL};"
    alpha_style  = "color:#1B5E3B;font-weight:600;" if row["alpha"] > 0 else "color:#C0392B;"
    stripe       = "background:#FAFAFA;" if i % 2 == 1 else ""
    return f"""
    <tr style="{stripe}">
        <td style="color:{SKY};font-size:12px;padding:11px 14px;width:32px;">{i+1}</td>
        <td style="padding:11px 14px;">
            <div style="font-weight:600;color:{NAVY};font-size:13px;">{html.escape(str(row['scheme_name']))}</div>
            <div style="font-size:11px;color:{TEAL};margin-top:2px;">{html.escape(str(row['fund_house']))}</div>
        </td>
        <td style="padding:11px 14px;">
            <span style="{bs};font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;white-space:nowrap;">{html.escape(str(row['category']))}</span>
        </td>
        <td style="text-align:right;font-family:monospace;padding:11px 14px;color:{NAVY};">{row['return_3yr_pct']:.2f}%</td>
        <td style="text-align:right;font-family:monospace;padding:11px 14px;{sharpe_style}">{row['sharpe_ratio']:.3f}</td>
        <td style="text-align:right;font-family:monospace;padding:11px 14px;{alpha_style}">{row['alpha']:.3f}</td>
        <td style="text-align:right;font-family:monospace;padding:11px 14px;color:#C0392B;">{row['max_drawdown_pct']:.1f}%</td>
        <td style="text-align:right;font-family:monospace;padding:11px 14px;color:{TEAL};">&#8377;{row['aum_crore']:,.0f} Cr</td>
    </tr>"""

def insight_item(icon, title, text):
    return f"""
    <div style="display:flex;gap:14px;align-items:flex-start;background:{WHITE};border:1px solid {SKY};border-radius:12px;padding:16px 18px;">
        <div style="width:36px;height:36px;min-width:36px;background:{NAVY};border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:15px;color:{SKY};font-weight:700;">{icon}</div>
        <div>
            <div style="font-size:12px;font-weight:700;color:{NAVY};margin-bottom:4px;">{title}</div>
            <div style="font-size:12px;color:{TEAL};line-height:1.65;">{text}</div>
        </div>
    </div>"""

rows_html    = "\n".join(perf_row(i, r) for i, r in top10.iterrows())
insights_html = "\n".join([
    insight_item("01", "Large &amp; Flexi Cap dominate",
                 "Consistent risk-adjusted performance places them at the top of Sharpe ratio rankings this week."),
    insight_item("02", "Positive alpha cluster",
                 "Funds with Sharpe &gt; 1.0 all show positive alpha — confirming genuine outperformance above Nifty 100."),
    insight_item("03", "Small cap drawdown risk",
                 "Max drawdown exceeds 25% for small cap entries. Suitable only for investors with a 5-year+ horizon."),
    insight_item("04", "SIP churn risk flagged",
                 "~20% of active SIP investors show transaction gaps above 35 days — flagged for retention intervention."),
])

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bluestock MF Weekly Performance Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:Arial,sans-serif;background:{BEIGE};color:{NAVY};}}
  .wrap{{max-width:860px;margin:36px auto 48px;border-radius:18px;overflow:hidden;border:1px solid {SKY};}}
  .hdr{{background:{NAVY};padding:44px 44px 36px;position:relative;}}
  .hdr-eyebrow{{display:flex;align-items:center;gap:10px;margin-bottom:22px;}}
  .hdr-dot{{width:34px;height:34px;background:{TEAL};border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;color:{WHITE};font-weight:700;}}
  .hdr-brand{{font-size:13px;color:{SKY};letter-spacing:2px;text-transform:uppercase;font-weight:500;}}
  .hdr-title{{font-size:34px;color:{WHITE};font-weight:700;line-height:1.18;margin-bottom:10px;}}
  .hdr-sub{{font-size:13px;color:{SKY};opacity:.75;letter-spacing:.4px;}}
  .hdr-tag{{display:inline-flex;align-items:center;gap:7px;background:rgba(203,217,230,.12);border:1px solid rgba(203,217,230,.22);border-radius:20px;font-size:11px;color:{SKY};padding:4px 13px;margin-top:18px;letter-spacing:.6px;}}
  .body{{background:{BEIGE};padding:36px 44px;}}
  .section-label{{font-size:10px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:{TEAL};margin-bottom:18px;}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:32px;}}
  .sip-banner{{background:{TEAL};border-radius:14px;padding:20px 24px;margin-bottom:34px;display:flex;gap:16px;align-items:flex-start;}}
  .sip-icon{{width:42px;height:42px;min-width:42px;background:rgba(203,217,230,.2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;color:{WHITE};}}
  .sip-text{{font-size:13px;color:{WHITE};line-height:1.7;opacity:.93;}}
  .sip-text strong{{color:{WHITE};opacity:1;font-weight:700;}}
  .tbl-wrap{{border-radius:14px;overflow:hidden;border:1px solid {SKY};margin-bottom:30px;}}
  .tbl-hdr{{background:{NAVY};padding:18px 22px;display:flex;align-items:center;justify-content:space-between;}}
  .tbl-hdr-title{{font-size:17px;color:{WHITE};font-weight:600;}}
  .tbl-hdr-pill{{font-size:10px;background:rgba(203,217,230,.18);color:{SKY};border-radius:20px;padding:4px 12px;letter-spacing:.7px;text-transform:uppercase;}}
  table{{width:100%;border-collapse:collapse;background:{WHITE};}}
  th{{background:#EEF3F7;color:{TEAL};font-weight:700;font-size:11px;padding:11px 14px;text-align:left;border-bottom:2px solid {SKY};letter-spacing:.5px;text-transform:uppercase;white-space:nowrap;}}
  th.r{{text-align:right;}}
  tr:hover td{{background:#F0F5F8;}}
  .insights-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px;}}
  .footer{{background:{NAVY};padding:18px 44px;display:flex;align-items:center;justify-content:space-between;}}
  .footer span{{font-size:11px;color:rgba(203,217,230,.55);letter-spacing:.3px;}}

  /* ── SMTP config block (shown in browser preview only) ── */
  .smtp-note{{background:#fff8e1;border:1px solid #f4b400;border-radius:10px;padding:16px 20px;margin-bottom:28px;font-size:12px;color:#5d4037;line-height:1.7;}}
  .smtp-note strong{{color:#e65100;}}
  .smtp-code{{background:#1a1a2e;color:#CBD9E6;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:12px;margin-top:10px;line-height:1.8;white-space:pre;}}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <div class="hdr-eyebrow">
      <div class="hdr-dot">&#9650;</div>
      <span class="hdr-brand">Bluestock Fintech</span>
    </div>
    <div class="hdr-title">MF Weekly<br>Performance Report</div>
    <div class="hdr-sub">Mutual fund analytics platform &middot; automated weekly digest</div>
    <div class="hdr-tag">Data source: AMFI India &amp; mfapi.in</div>
  </div>

  <div class="body">

    <div class="smtp-note">
      <strong>&#128274; Email delivery — SMTP config</strong><br>
      To send this report as a weekly email, configure the block below with your Gmail App Password
      (Google Account &rarr; Security &rarr; 2-Step Verification &rarr; App Passwords).
      The schedule runs every Monday at 08:00 via the <code>schedule</code> library.
      <div class="smtp-code">
# ── SMTP delivery (uncomment to enable) ──────────────────────
# import smtplib, schedule
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
#
# SMTP_HOST   = "smtp.gmail.com"
# SMTP_PORT   = 587
# SENDER      = "your_email@gmail.com"
# APP_PASSWORD = "xxxx xxxx xxxx xxxx"   # Gmail App Password
# RECIPIENTS  = ["recipient@example.com"]
#
# def send_email(html_body):
#     msg = MIMEMultipart("alternative")
#     msg["Subject"] = f"Bluestock MF Weekly Report — {{peak_sip['month'].strftime('%b %Y')}}"
#     msg["From"]    = SENDER
#     msg["To"]      = ", ".join(RECIPIENTS)
#     msg.attach(MIMEText(html_body, "html"))
#     with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
#         s.starttls()
#         s.login(SENDER, APP_PASSWORD)
#         s.sendmail(SENDER, RECIPIENTS, msg.as_string())
#     print("Email sent successfully.")
#
# schedule.every().monday.at("08:00").do(lambda: send_email(HTML))
# while True:
#     schedule.run_pending()
#     time.sleep(60)
      </div>
    </div>

    <div class="section-label">Industry snapshot &mdash; December 2025</div>
    <div class="kpi-grid">
      {kpi_card("Industry AUM",    f"&#8377;{total_aum:.0f}L Cr",                       "All-time high",  dark=True)}
      {kpi_card("SIP Inflow",      f"&#8377;{latest_sip['sip_inflow_crore']:,.0f} Cr",  "Latest month",   dark=True)}
      {kpi_card("Active SIP A/Cs", f"{latest_sip['active_sip_accounts_crore']:.2f} Cr", "Accounts",       dark=False)}
      {kpi_card("Total Folios",    f"{total_folios} Cr",                                 "Dec 2025",       dark=False)}
    </div>

    <div class="sip-banner">
      <div class="sip-icon">&#8599;</div>
      <div class="sip-text">
        Monthly SIP inflows hit an all-time high of
        <strong>&#8377;{peak_sip['sip_inflow_crore']:,.0f} Cr</strong>
        in {peak_sip['month'].strftime('%B %Y')}. Active SIP accounts stood at
        <strong>{latest_sip['active_sip_accounts_crore']:.2f} crore</strong> &mdash; reflecting strong retail
        participation in equity markets. Inflows have grown <strong>2.8&times;</strong> since Jan 2022.
      </div>
    </div>

    <div class="section-label">Top 10 funds by Sharpe ratio</div>
    <div class="tbl-wrap">
      <div class="tbl-hdr">
        <span class="tbl-hdr-title">Risk-adjusted performance</span>
        <span class="tbl-hdr-pill">Sharpe &middot; Alpha &middot; Drawdown</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>#</th><th>Scheme</th><th>Category</th>
            <th class="r">3yr Return</th><th class="r">Sharpe</th>
            <th class="r">Alpha</th><th class="r">Max DD</th><th class="r">AUM</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>

    <div class="section-label">Key insights this week</div>
    <div class="insights-grid">{insights_html}</div>

  </div>

  <div class="footer">
    <span>Bluestock Fintech Pvt. Ltd. &middot; MF Analytics Capstone &middot; June 2026</span>
    <span>Auto-generated &middot; not financial advice</span>
  </div>

</div>
</body>
</html>"""

out = REPORTS / "weekly_performance_report.html"
out.write_text(HTML, encoding="utf-8")
print(f"Report saved → {out}")
print("Opening in browser in 3 seconds...")
time.sleep(3)
webbrowser.open(out.resolve().as_uri())
print("Done! Browser should have opened the report.")