import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(
    page_title="Bluestock MF Analytics",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROJECT_DIR   = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"

PALETTE = ["#C18DB4","#87A7D0","#27425D","#E2CAD8","#0E1B48",
           "#87A7D0","#C18DB4","#0E1F2F","#E2CAD8","#27425D"]

HEADER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Hide sidebar entirely */
[data-testid="stSidebar"] {display: none !important}
[data-testid="collapsedControl"] {display: none !important}

/* Main background */
.stApp {background: #0E1B48 !important}
section[data-testid="stMain"] > div {padding-top: 0 !important}

.topnav-wrap {
    background: #0E1F2F;
    border-bottom: 1px solid #27425D;
    padding: 14px 24px 10px 24px;
    margin-bottom: 0;
}
.topnav-brand {
    font-size: 15px;
    font-weight: 700;
    color: #E2CAD8;
    letter-spacing: 0.04em;
    display: inline-block;
}
div[data-testid="stHorizontalBlock"]:has(button[key^="nav_"]) {
    background: #0E1F2F;
    border-bottom: 1px solid #27425D;
    padding: 0 8px;
    margin-bottom: 20px !important;
    gap: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key^="nav_"]) button {
    background: transparent !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    color: #87A7D0 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 10px 4px !important;
    box-shadow: none !important;
    font-family: "Inter", sans-serif !important;
}
div[data-testid="stHorizontalBlock"]:has(button[key^="nav_"]) button:hover {
    color: #E2CAD8 !important;
    border-bottom: 3px solid #C18DB4 !important;
    background: transparent !important;
}

/* Metric cards */
.metric-card {
    background: #0E1F2F;
    border-radius: 10px;
    padding: 18px 20px;
    border-left: 4px solid #C18DB4;
    margin-bottom: 4px;
}
.metric-val  {font-size: 26px; font-weight: 600; color: #C18DB4; line-height: 1.1;}
.metric-lbl  {font-size: 12px; color: #87A7D0; margin-top: 3px;}
.metric-sub  {font-size: 11px; color: #E2CAD8; margin-top: 2px;}

/* Page titles */
.page-title  {font-size: 22px; font-weight: 600; color: #E2CAD8; margin-bottom: 4px;}
.page-sub    {font-size: 13px; color: #87A7D0; margin-bottom: 18px;}

/* Section headings */
h4 {color: #E2CAD8 !important;}

/* Sidebar filter area (now shown inline via st.expander if needed) */
[data-testid="stExpander"] {background: #0E1F2F !important; border: 1px solid #27425D !important; border-radius: 8px;}

div[data-testid="stHorizontalBlock"] > div {min-width: 0;}

/* Dataframe */
[data-testid="stDataFrame"] {border: 1px solid #27425D; border-radius: 8px;}

/* Streamlit radio buttons for nav (hidden, we use HTML nav) */
[data-testid="stVerticalBlock"] > div:first-child .stRadio {display:none}

/* Selectbox / multiselect labels */
label {color: #87A7D0 !important; font-size: 12px !important;}

/* Divider */
hr {border-color: #27425D !important;}

/* Caption */
.stCaption {color: #87A7D0 !important;}
</style>
"""
st.markdown(HEADER_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(name):
    for pattern in [f"clean_{name}.csv", f"{name}.csv",
                    f"0?_{name}.csv", f"0?_*{name}*.csv"]:
        matches = list(PROCESSED_DIR.glob(pattern))
        if not matches:
            matches = list((PROJECT_DIR / "data" / "raw").glob(pattern))
        if matches:
            return pd.read_csv(matches[0], low_memory=False)
    raw = PROJECT_DIR / "data" / "raw"
    for f in raw.iterdir():
        if name.replace("_","").lower() in f.stem.replace("_","").lower():
            return pd.read_csv(f, low_memory=False)
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_all():
    nav    = load("nav_history");         fund_master = load("fund_master")
    aum    = load("aum_by_fund_house");   sip         = load("monthly_sip_inflows")
    cat_in = load("category_inflows");    folios      = load("industry_folio_count")
    txn    = load("investor_transactions"); perf       = load("scheme_performance")
    bench  = load("benchmark_indices");   sc          = load("fund_scorecard")

    for df, cols in [(nav,["date","nav"]),(aum,["date"]),(sip,["month"]),
                     (cat_in,["month"]),(folios,["month"]),(txn,["transaction_date"]),
                     (bench,["date"])]:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")

    for df, cols in [(nav,["nav"]),(txn,["amount_inr"]),(bench,["close_value"]),
                     (aum,["aum_lakh_crore","aum_crore"]),(sip,["sip_inflow_crore"])]:
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    if not fund_master.empty and not nav.empty:
        nav["amfi_code"]         = nav["amfi_code"].astype(str)
        fund_master["amfi_code"] = fund_master["amfi_code"].astype(str)
        nav = nav.merge(
            fund_master[["amfi_code","scheme_name","fund_house",
                          "category","sub_category","risk_category",
                          "expense_ratio_pct"]],
            on="amfi_code", how="left")

    if not perf.empty and not fund_master.empty:
        perf["amfi_code"] = perf["amfi_code"].astype(str)
        for c in ["return_1yr_pct","return_3yr_pct","return_5yr_pct",
                  "sharpe_ratio","alpha","beta","std_dev_ann_pct",
                  "max_drawdown_pct","aum_crore","expense_ratio_pct"]:
            if c in perf.columns:
                perf[c] = pd.to_numeric(perf[c], errors="coerce")
        perf = perf.merge(
    fund_master[["amfi_code","sub_category","risk_category"]],
    on="amfi_code",
    how="left"
)

    return nav, fund_master, aum, sip, cat_in, folios, txn, perf, bench, sc


nav, funds, aum, sip, cat_in, folios, txn, perf, bench, sc = load_all()


def metric_card(val, label, sub=""):
    return f"""<div class="metric-card">
        <div class="metric-val">{val}</div>
        <div class="metric-lbl">{label}</div>
        {"<div class='metric-sub'>"+sub+"</div>" if sub else ""}
    </div>"""


# ── Top navigation bar ──────────────────────────────────────────────────────
PAGES = ["Industry Overview", "Fund Performance", "Investor Analytics", "SIP & Market Trends"]

if "page_idx" not in st.session_state:
    st.session_state.page_idx = 0

# Render brand + nav buttons inside a styled container
st.markdown('<div class="topnav-wrap"><span class="topnav-brand">Bluestock MF</span></div>', unsafe_allow_html=True)

nav_cols = st.columns([2, 1, 1, 1, 1])
for i, label in enumerate(PAGES):
    is_active = st.session_state.page_idx == i
    btn_style = "nav-btn-active" if is_active else "nav-btn"
    if nav_cols[i + 1].button(label, key=f"nav_{i}", use_container_width=True):
        st.session_state.page_idx = i
        st.rerun()

page = PAGES[st.session_state.page_idx]

# ── Inline filters (shown below navbar when relevant) ───────────────────────
fh_opts    = sorted(funds["fund_house"].dropna().unique().tolist()) if not funds.empty else []
cat_opts   = sorted(funds["category"].dropna().unique().tolist())   if not funds.empty else []
state_opts = sorted(txn["state"].dropna().unique().tolist())         if not txn.empty  else []

sel_fh = []; sel_cat = []; sel_state = []; sel_tier = "All"; sel_age = []; yr_range = (2022, 2025)

if page == "Fund Performance":
    with st.expander("Filters", expanded=False):
        fc1, fc2 = st.columns(2)
        sel_fh  = fc1.multiselect("Fund House", fh_opts,  default=[])
        sel_cat = fc2.multiselect("Category",   cat_opts, default=[])

elif page == "Investor Analytics":
    with st.expander("Filters", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        sel_state = fc1.multiselect("State", state_opts, default=[])
        sel_tier  = fc2.selectbox("City Tier", ["All","T30","B30"])
        sel_age   = fc3.multiselect("Age Group",
                        sorted(txn["age_group"].dropna().unique().tolist()) if not txn.empty else [])

elif page == "SIP & Market Trends":
    with st.expander("Year Range", expanded=False):
        yr_range = st.slider("Year", 2022, 2025, (2022, 2025))

st.caption("Bluestock Fintech Capstone · June 2026")


if page == "Industry Overview":
    st.markdown('<div class="page-title">Industry Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Indian Mutual Fund Industry — Key Metrics as of December 2025</div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(metric_card("₹81 L Cr",  "Total Industry AUM",  "+18% YoY"), unsafe_allow_html=True)
    c2.markdown(metric_card("₹31,002 Cr","Monthly SIP Inflows",  "All-time high Dec 2025"), unsafe_allow_html=True)
    c3.markdown(metric_card("26.12 Cr",  "Total Folios",          "2× growth since 2022"), unsafe_allow_html=True)
    c4.markdown(metric_card("1,908",     "Active Schemes",        "AMFI registered"), unsafe_allow_html=True)

    st.markdown("---")
    col1, col2 = st.columns([3,2])

    with col1:
        st.markdown("#### Industry AUM Trend (2022–2025)")
        if not aum.empty and "aum_lakh_crore" in aum.columns:
            aum_col = "aum_lakh_crore"
            aum_trend = (aum.dropna(subset=["date",aum_col])
                         .groupby("date")[aum_col].sum().reset_index()
                         .sort_values("date"))
            fig = px.area(aum_trend, x="date", y=aum_col,
                          color_discrete_sequence=["#C18DB4"],
                          labels={"date":"","aum_lakh_crore":"AUM (₹ Lakh Crore)"})
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                               plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", showlegend=False)
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Place 03_aum_by_fund_house.csv in data/raw/ to see AUM trend.")

    with col2:
        st.markdown("#### Top 10 AMCs by Peak AUM")
        if not aum.empty:
            aum_col = "aum_lakh_crore" if "aum_lakh_crore" in aum.columns else "aum_crore"
            top_amc = (aum.dropna(subset=["fund_house",aum_col])
                       .groupby("fund_house")[aum_col].max()
                       .sort_values(ascending=True).tail(10)
                       .reset_index())
            fig = px.bar(top_amc, y="fund_house", x=aum_col, orientation="h",
                         color_discrete_sequence=["#87A7D0"],
                         labels={"fund_house":"","aum_lakh_crore":"₹ Lakh Crore"})
            fig.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                               plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8")
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(color="#87A7D0", tickfont=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("#### Monthly SIP Inflow Trend")
        if not sip.empty and "sip_inflow_crore" in sip.columns:
            sip_plot = sip.dropna(subset=["month","sip_inflow_crore"]).sort_values("month")
            peak     = sip_plot.loc[sip_plot["sip_inflow_crore"].idxmax()]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=sip_plot["month"], y=sip_plot["sip_inflow_crore"],
                fill="tozeroy", fillcolor="rgba(193,141,180,0.15)",
                line=dict(color="#C18DB4",width=2), name="SIP Inflow"))
            fig.add_annotation(x=peak["month"], y=peak["sip_inflow_crore"],
                               text=f"₹{peak['sip_inflow_crore']:,.0f} Cr",
                               showarrow=True, arrowhead=2, arrowcolor="#E2CAD8",
                               font=dict(color="#E2CAD8",size=10), ax=30, ay=-35)
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0),
                               plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", showlegend=False)
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0", tickprefix="₹")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.markdown("#### Folio Count Growth")
        if not folios.empty and "total_folios_cr" in folios.columns:
            fol_plot = folios.dropna(subset=["month","total_folios_cr"]).sort_values("month")
            fol_plot["total_folios_cr"] = pd.to_numeric(fol_plot["total_folios_cr"], errors="coerce")
            fig = px.line(fol_plot, x="month", y="total_folios_cr",
                          color_discrete_sequence=["#C18DB4"],
                          labels={"month":"","total_folios_cr":"Folios (Crore)"})
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0),
                               plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", showlegend=False)
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0")
            st.plotly_chart(fig, use_container_width=True)


elif page == "Fund Performance":
    st.markdown('<div class="page-title">Fund Performance Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Risk-adjusted returns, scorecard, NAV trends and benchmark comparison</div>', unsafe_allow_html=True)

    perf_f = perf.copy()
    if sel_fh:
        perf_f = perf_f[perf_f["fund_house"].isin(sel_fh)]
    if sel_cat:
        perf_f = perf_f[perf_f["category"].isin(sel_cat)]

    col1, col2 = st.columns([3,2])
    with col1:
        st.markdown("#### Risk vs Return Bubble Chart")
        if not perf_f.empty:
            bubble = perf_f.dropna(subset=["return_3yr_pct","std_dev_ann_pct","aum_crore"])
            if len(bubble):
                fig = px.scatter(
                    bubble, x="std_dev_ann_pct", y="return_3yr_pct",
                    size="aum_crore", color="category",
                    hover_name="scheme_name",
                    hover_data={"sharpe_ratio":True,"fund_house":True,
                                "aum_crore":True,"std_dev_ann_pct":True},
                    color_discrete_sequence=PALETTE, size_max=45,
                    labels={"std_dev_ann_pct":"Risk — Std Dev (%)","return_3yr_pct":"3-Year CAGR (%)"},
                )
                fig.update_layout(height=380, plot_bgcolor="#0E1B48",
                                   paper_bgcolor="#0E1B48", font_color="#E2CAD8",
                                   legend=dict(font=dict(size=10)))
                fig.update_xaxes(showgrid=False, color="#87A7D0")
                fig.update_yaxes(gridcolor="#27425D", color="#87A7D0")
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Fund Scorecard")
        if not perf_f.empty:
            disp_cols = ["scheme_name","category","return_3yr_pct","sharpe_ratio","alpha"]
            avail = [c for c in disp_cols if c in perf_f.columns]
            sc_tbl = perf_f[avail].dropna(subset=["return_3yr_pct"]).sort_values("return_3yr_pct",ascending=False)
            if "return_3yr_pct" in sc_tbl.columns:
                sc_tbl["return_3yr_pct"] = sc_tbl["return_3yr_pct"].round(2)
            if "sharpe_ratio" in sc_tbl.columns:
                sc_tbl["sharpe_ratio"] = sc_tbl["sharpe_ratio"].round(4)
            if "alpha" in sc_tbl.columns:
                sc_tbl["alpha"] = (sc_tbl["alpha"] * 100).round(4)
            sc_tbl.columns = [c.replace("_pct","").replace("_"," ").title() for c in sc_tbl.columns]
            st.dataframe(sc_tbl.reset_index(drop=True), height=380, use_container_width=True)

    st.markdown("---")
    st.markdown("#### NAV Trend — Select a Fund")
    if not nav.empty and not funds.empty:
        all_schemes = sorted(nav["scheme_name"].dropna().unique().tolist())
        sel_fund = st.selectbox("Fund", all_schemes, label_visibility="collapsed")
        if sel_fund:
            fund_nav = nav[nav["scheme_name"]==sel_fund].sort_values("date")
            bench_n100 = (bench[bench["index_name"].str.contains("Nifty 100",na=False)]
                          .sort_values("date") if not bench.empty else pd.DataFrame())

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=fund_nav["date"], y=fund_nav["nav"],
                name=sel_fund[:30], line=dict(color="#C18DB4",width=2)))
            if not bench_n100.empty:
                start_nav  = fund_nav["nav"].iloc[0]  if len(fund_nav)  else 1
                start_ben  = bench_n100["close_value"].iloc[0] if len(bench_n100) else 1
                scaled_ben = bench_n100["close_value"] / start_ben * start_nav
                fig.add_trace(go.Scatter(
                    x=bench_n100["date"], y=scaled_ben,
                    name="Nifty 100 (scaled)", line=dict(color="#E2CAD8",width=1.5,dash="dash")))
            fig.update_layout(height=280, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", hovermode="x unified",
                               margin=dict(l=0,r=0,t=10,b=0),
                               legend=dict(font=dict(size=10)))
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0", tickprefix="₹")
            st.plotly_chart(fig, use_container_width=True)


elif page == "Investor Analytics":
    st.markdown('<div class="page-title">Investor Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Transaction patterns, demographics, geography and SIP behaviour</div>', unsafe_allow_html=True)

    txn_f = txn.copy()
    if "sel_state" in dir() and sel_state:
        txn_f = txn_f[txn_f["state"].isin(sel_state)]
    if "sel_tier" in dir() and sel_tier != "All":
        txn_f = txn_f[txn_f["city_tier"] == sel_tier]
    if "sel_age" in dir() and sel_age:
        txn_f = txn_f[txn_f["age_group"].isin(sel_age)]

    m1,m2,m3,m4 = st.columns(4)
    total_inv  = txn_f["amount_inr"].sum() if not txn_f.empty else 0
    num_inv    = txn_f["investor_id"].nunique() if not txn_f.empty and "investor_id" in txn_f.columns else 0
    avg_sip    = txn_f[txn_f["transaction_type"]=="SIP"]["amount_inr"].mean() if not txn_f.empty else 0
    verified   = (txn_f["kyc_status"]=="Verified").mean()*100 if not txn_f.empty and "kyc_status" in txn_f.columns else 0
    m1.markdown(metric_card(f"₹{total_inv/1e9:.1f}B","Total Transactions"), unsafe_allow_html=True)
    m2.markdown(metric_card(f"{num_inv:,}","Unique Investors"), unsafe_allow_html=True)
    m3.markdown(metric_card(f"₹{avg_sip:,.0f}","Avg SIP Amount"), unsafe_allow_html=True)
    m4.markdown(metric_card(f"{verified:.1f}%","KYC Verified"), unsafe_allow_html=True)

    st.markdown("---")
    col1,col2 = st.columns(2)
    with col1:
        st.markdown("#### Transaction Volume by State")
        if not txn_f.empty and "state" in txn_f.columns:
            st_data = (txn_f.groupby("state")["amount_inr"].sum()
                       .sort_values(ascending=True).tail(15).reset_index())
            fig = px.bar(st_data, y="state", x="amount_inr", orientation="h",
                         color_discrete_sequence=["#87A7D0"],
                         labels={"state":"","amount_inr":"Total Amount (₹)"})
            fig.update_layout(height=350, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", margin=dict(l=0,r=0,t=10,b=0))
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(color="#87A7D0", tickfont=dict(size=9))
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### SIP / Lumpsum / Redemption Split")
        if not txn_f.empty and "transaction_type" in txn_f.columns:
            txn_type = txn_f["transaction_type"].value_counts().reset_index()
            txn_type.columns = ["type","count"]
            fig = px.pie(txn_type, names="type", values="count",
                         color_discrete_sequence=["#C18DB4","#87A7D0","#27425D"],
                         hole=0.45)
            fig.update_layout(height=350, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", margin=dict(l=0,r=20,t=10,b=0),
                               legend=dict(font=dict(size=11)))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col3,col4 = st.columns(2)
    with col3:
        st.markdown("#### Age Group vs Average SIP Amount")
        if not txn_f.empty:
            sip_age = (txn_f[txn_f["transaction_type"]=="SIP"]
                       .groupby("age_group")["amount_inr"].mean()
                       .sort_index().reset_index())
            fig = px.bar(sip_age, x="age_group", y="amount_inr",
                         color_discrete_sequence=PALETTE,
                         labels={"age_group":"Age Group","amount_inr":"Avg SIP (₹)"})
            fig.update_layout(height=280, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", margin=dict(l=0,r=0,t=10,b=0))
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0", tickprefix="₹")
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.markdown("#### Monthly Transaction Volume")
        if not txn_f.empty and "transaction_date" in txn_f.columns:
            txn_f2 = txn_f.copy()
            txn_f2["month"] = txn_f2["transaction_date"].dt.to_period("M").astype(str)
            mv = (txn_f2.groupby(["month","transaction_type"])["amount_inr"]
                  .sum().unstack(fill_value=0).sort_index())
            fig = go.Figure()
            colors_map = {"SIP":"#C18DB4","Lumpsum":"#87A7D0","Redemption":"#27425D"}
            for col_name in mv.columns:
                fig.add_trace(go.Bar(x=mv.index, y=mv[col_name],
                                     name=col_name, marker_color=colors_map.get(col_name,"#888780")))
            fig.update_layout(barmode="stack", height=280, plot_bgcolor="#0E1B48",
                               paper_bgcolor="#0E1B48", font_color="#E2CAD8",
                               margin=dict(l=0,r=0,t=10,b=0), legend=dict(font=dict(size=10)))
            fig.update_xaxes(showgrid=False, color="#87A7D0", tickangle=45, tickfont=dict(size=8))
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0", tickprefix="₹")
            st.plotly_chart(fig, use_container_width=True)


elif page == "SIP & Market Trends":
    st.markdown('<div class="page-title">SIP & Market Trends</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">SIP flows vs market performance, category inflows, FY25 net flow analysis</div>', unsafe_allow_html=True)

    col1,col2 = st.columns([3,2])
    with col1:
        st.markdown("#### SIP Inflow vs Nifty 50 (Dual Axis)")
        if not sip.empty and not bench.empty:
            sip_yr = sip.dropna(subset=["month","sip_inflow_crore"]).copy()
            sip_yr = sip_yr[(sip_yr["month"].dt.year >= yr_range[0]) &
                            (sip_yr["month"].dt.year <= yr_range[1])].sort_values("month")

            n50 = (bench[bench["index_name"].str.contains("Nifty 50",na=False)]
                   .sort_values("date")
                   .set_index("date")["close_value"]
                   .resample("ME").last().reset_index())
            n50 = n50[(n50["date"].dt.year >= yr_range[0]) &
                      (n50["date"].dt.year <= yr_range[1])]

            fig = make_subplots(specs=[[{"secondary_y":True}]])
            fig.add_trace(go.Bar(
                x=sip_yr["month"], y=sip_yr["sip_inflow_crore"],
                name="SIP Inflow (₹ Cr)", marker_color="#C18DB4", opacity=0.8),
                secondary_y=False)
            fig.add_trace(go.Scatter(
                x=n50["date"], y=n50["close_value"],
                name="Nifty 50", line=dict(color="#87A7D0",width=2)),
                secondary_y=True)
            fig.update_layout(height=350, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", hovermode="x unified",
                               margin=dict(l=0,r=0,t=10,b=0),
                               legend=dict(font=dict(size=10)))
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(gridcolor="#27425D", color="#87A7D0",secondary_y=False, tickprefix="₹")
            fig.update_yaxes(color="#87A7D0", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Top 5 Categories by Net Inflow (FY25)")
        _ic = next((c for c in cat_in.columns if "inflow" in c.lower() or "net" in c.lower()), None)
        if not cat_in.empty and _ic:
            ci = cat_in.copy()
            ci["month"] = pd.to_datetime(ci["month"], errors="coerce")
            ci["net_inflow_cr"] = pd.to_numeric(ci[_ic], errors="coerce")
            fy25 = ci[(ci["month"] >= "2024-04-01") & (ci["month"] <= "2025-03-31")]
            top5cat = (fy25.groupby("category")["net_inflow_cr"].sum()
                       .sort_values(ascending=False).head(5).reset_index())
            fig = px.bar(top5cat, y="category", x="net_inflow_cr", orientation="h",
                         color="net_inflow_cr", color_continuous_scale=["#0E1B48","#C18DB4"],
                         labels={"category":"","net_inflow_cr":"Net Inflow (₹ Cr)"})
            fig.update_layout(height=350, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", coloraxis_showscale=False,
                               margin=dict(l=0,r=0,t=10,b=0))
            fig.update_xaxes(showgrid=False, color="#87A7D0")
            fig.update_yaxes(color="#87A7D0")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Category Inflow Heatmap")
    _inflow_col = next((c for c in cat_in.columns if "inflow" in c.lower() or "net" in c.lower()), None)
    if not cat_in.empty and _inflow_col:
        ci2 = cat_in.copy()
        ci2["month"] = pd.to_datetime(ci2["month"], errors="coerce")
        ci2["net_inflow_cr"] = pd.to_numeric(ci2[_inflow_col], errors="coerce")
        ci2 = ci2[(ci2["month"].dt.year >= yr_range[0]) &
                  (ci2["month"].dt.year <= yr_range[1])]
        ci2["month_lbl"] = ci2["month"].dt.strftime("%b %Y")
        piv = ci2.pivot_table(index="category", columns="month_lbl",
                               values="net_inflow_cr", aggfunc="sum")
        mo  = (ci2.drop_duplicates("month_lbl").sort_values("month")["month_lbl"].tolist())
        piv = piv.reindex(columns=[m for m in mo if m in piv.columns])
        if not piv.empty:
            fig = px.imshow(piv, color_continuous_scale="RdYlGn",
                            color_continuous_midpoint=0,
                            labels=dict(x="Month", y="Category", color="Net Inflow (₹Cr)"),
                            aspect="auto")
            fig.update_layout(height=320, plot_bgcolor="#0E1B48", paper_bgcolor="#0E1B48",
                               font_color="#E2CAD8", margin=dict(l=0,r=0,t=10,b=0))
            fig.update_xaxes(tickangle=45, tickfont=dict(size=9), color="#87A7D0")
            fig.update_yaxes(tickfont=dict(size=9), color="#87A7D0")
            st.plotly_chart(fig, use_container_width=True)