"""
MSBA 305 – E-Commerce Analytics Dashboard
Streamlit app with role-based access control.

Credentials:
  manager   / 123  → full dashboard (all 9 panels + governance)
  marketing / 456  → campaign-relevant analytics only

Expected CSV files (same directory as app.py):
  cleaned_transactions.csv
  cleaned_products.csv
  cleaned_copurchase.csv
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="E-Commerce Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Auth ────────────────────────────────────────────────────────────────────
CREDENTIALS = {
    "manager":   {"password": "123",  "role": "Manager"},
    "marketing": {"password": "456",  "role": "Marketing"},
}

def login():
    st.title("🛒 E-Commerce Analytics Dashboard")
    st.subheader("Please log in to continue")
    with st.form("login_form"):
        username = st.text_input("Username").strip().lower()
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        user = CREDENTIALS.get(username)
        if user and user["password"] == password:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["role"] = user["role"]
            st.rerun()
        else:
            st.error("Invalid username or password.")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
    st.stop()

role     = st.session_state["role"]
username = st.session_state["username"]

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shop.png", width=60)
    st.markdown(f"### Welcome, **{username}**")
    st.markdown(f"Role: `{role}`")
    st.divider()
    if st.button("🚪 Logout"):
        for k in ["logged_in", "username", "role"]:
            st.session_state.pop(k, None)
        st.rerun()

# ─── Data Loading ─────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

@st.cache_data
def load_transactions():
    path = os.path.join(BASE, "cleaned_transactions.csv")
    df = pd.read_csv(path, parse_dates=["invoice_date"], low_memory=False)
    df.columns = df.columns.str.strip().str.lower()
    return df

@st.cache_data
def load_products():
    path = os.path.join(BASE, "cleaned_products.csv")
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.strip().str.lower()
    return df

@st.cache_data
def load_copurchase():
    path = os.path.join(BASE, "cleaned_copurchase.csv")
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.strip().str.lower()
    return df

def try_load(loader):
    try:
        return loader(), None
    except FileNotFoundError as e:
        return None, str(e)

df_t, err_t = try_load(load_transactions)
df_p, err_p = try_load(load_products)
df_c, err_c = try_load(load_copurchase)

missing = [m for m, e in [("cleaned_transactions.csv", err_t),
                            ("cleaned_products.csv",    err_p),
                            ("cleaned_copurchase.csv",  err_c)] if e]
if missing:
    st.error(
        f"⚠️ Missing CSV file(s): **{', '.join(missing)}**\n\n"
        "Place the exported CSVs from your notebook in the same folder as `app.py` and restart."
    )
    st.stop()

# ─── Helper: revenue column ──────────────────────────────────────────────────
def rev_col(df):
    for c in ["total_price_gbp", "revenue", "total_revenue", "total_price"]:
        if c in df.columns:
            return c
    raise KeyError("Cannot find revenue column. Expected 'total_price_gbp'.")

REV = rev_col(df_t)

# ─── KPI Row ─────────────────────────────────────────────────────────────────
def kpi_row():
    total_rev    = df_t[REV].sum()
    total_orders = df_t["invoice_no"].nunique() if "invoice_no" in df_t.columns else 0
    total_cust   = df_t["customer_id"].nunique() if "customer_id" in df_t.columns else 0
    total_sku    = df_t["stock_code"].nunique()  if "stock_code"  in df_t.columns else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total Revenue",   f"£{total_rev:,.0f}")
    k2.metric("🧾 Invoices",        f"{total_orders:,}")
    k3.metric("👤 Customers",       f"{total_cust:,}")
    k4.metric("📦 Unique SKUs",     f"{total_sku:,}")

# ═══════════════════════════════════════════════════════════════════════════════
#  MANAGER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def manager_dashboard():
    st.title("🛒 E-Commerce Analytics Dashboard")
    st.caption("Online Retail Dataset (Dec 2010 – Dec 2011) | Role: **Manager** — Full Access")
    kpi_row()
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Revenue Analytics",
        "🛍️ Product Intelligence",
        "🔗 Co-Purchase Graph",
        "🔒 Governance",
    ])

    # ── Tab 1 : Revenue Analytics ────────────────────────────────────────────
    with tab1:
        st.subheader("Revenue Analytics (SQLite / Transactions)")

        col_left, col_right = st.columns(2)

        # Panel 1 – Monthly Revenue
        with col_left:
            if "invoice_date" in df_t.columns:
                df_m = df_t.copy()
                df_m["month"] = df_m["invoice_date"].dt.to_period("M").astype(str)
                monthly = df_m.groupby("month")[REV].sum().reset_index()
                monthly.columns = ["month", "revenue"]
                peak = monthly["revenue"].idxmax()
                colors = ["#e04c2f" if i == peak else "#4da8c7" for i in range(len(monthly))]
                fig = go.Figure(go.Bar(x=monthly["month"], y=monthly["revenue"],
                                       marker_color=colors,
                                       hovertemplate="£%{y:,.0f}<extra></extra>"))
                fig.update_layout(title="Monthly Revenue (£)", xaxis_tickangle=-45,
                                  yaxis_tickformat="£,.0f", height=350)
                st.plotly_chart(fig, use_container_width=True)
                st.caption("🔴 Red bar = peak month (Nov 2011). Q4 seasonality clearly visible.")

        # Panel 6 – Day of Week
        with col_right:
            if "invoice_date" in df_t.columns:
                df_t["dow"] = df_t["invoice_date"].dt.day_name()
                order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                dow = df_t.groupby("dow")[REV].sum().reindex(order).reset_index()
                dow.columns = ["day", "revenue"]
                weekend = ["Saturday","Sunday"]
                dow["color"] = dow["day"].apply(lambda d: "#c7c7c7" if d in weekend else "#4da8c7")
                fig2 = go.Figure(go.Bar(x=dow["day"], y=dow["revenue"],
                                        marker_color=dow["color"],
                                        hovertemplate="£%{y:,.0f}<extra></extra>"))
                fig2.update_layout(title="Revenue by Day of Week",
                                   yaxis_tickformat="£,.0f", height=350)
                st.plotly_chart(fig2, use_container_width=True)
                st.caption("Business operates Mon–Fri only. Tue/Wed are highest-revenue days.")

        col3, col4 = st.columns(2)

        # Panel 2 – Revenue by Country
        with col3:
            if "country" in df_t.columns:
                top10 = df_t.groupby("country")[REV].sum().sort_values(ascending=False).head(10)
                fig3 = px.bar(top10[::-1], orientation="h",
                              labels={"value":"Revenue (£)", "index":"Country"},
                              title="Revenue by Country (Top 10)",
                              color=top10[::-1].values,
                              color_continuous_scale="Blues")
                fig3.update_layout(height=380, coloraxis_showscale=False,
                                   xaxis_tickformat="£,.0f")
                st.plotly_chart(fig3, use_container_width=True)
                st.caption("UK represents >80% of revenue. Germany/France/Ireland are growth targets.")

        # Panel 9 – Guest vs Registered
        with col4:
            if "is_guest" in df_t.columns:
                grp = df_t.groupby("is_guest")[REV].sum().reset_index()
                grp["label"] = grp["is_guest"].map({0: "Registered", 1: "Guest"})
                grp["pct"] = (grp[REV] / grp[REV].sum() * 100).round(1)
                fig4 = px.bar(grp, x="label", y=REV,
                              color="label", color_discrete_map={"Registered":"steelblue","Guest":"coral"},
                              text=grp["pct"].astype(str) + "%",
                              title="Revenue: Guest vs Registered Customers",
                              labels={REV:"Revenue (£)", "label":""})
                fig4.update_traces(textposition="inside", textfont_size=14)
                fig4.update_layout(showlegend=False, height=350, yaxis_tickformat="£,.0f")
                st.plotly_chart(fig4, use_container_width=True)
                st.caption("Registered customers drive ~85% of revenue. Guest conversion is a key growth lever.")

        # Panel 4 – Customer Segments
        if "customer_id" in df_t.columns:
            st.subheader("Customer Lifecycle Segmentation")
            registered = df_t[df_t.get("is_guest", pd.Series(0, index=df_t.index)) != 1]
            if "invoice_no" in registered.columns:
                seg_counts = registered.groupby("customer_id")["invoice_no"].nunique()
                def segment(n):
                    if n == 1:   return "One-time"
                    if n <= 5:   return "Occasional (2-5)"
                    if n <= 15:  return "Regular (6-15)"
                    return "Loyal (16+)"
                seg_df = seg_counts.apply(segment).value_counts().reset_index()
                seg_df.columns = ["Segment", "Count"]
                fig5 = px.pie(seg_df, names="Segment", values="Count",
                              title="Customer Segments (Registered Only)",
                              color_discrete_sequence=px.colors.sequential.Blues_r)
                fig5.update_traces(textposition="inside", textinfo="percent+label")
                fig5.update_layout(height=380)
                st.plotly_chart(fig5, use_container_width=True)
                st.caption("Most customers are one-time buyers. Retention programs are the highest-ROI lever.")

    # ── Tab 2 : Product Intelligence ─────────────────────────────────────────
    with tab2:
        st.subheader("Product Intelligence (MongoDB / Catalog)")

        col_a, col_b = st.columns(2)

        # Panel 3 – Top 10 Products by Units Sold
        with col_a:
            if "description" in df_t.columns and "quantity" in df_t.columns:
                tp = df_t.groupby("description")["quantity"].sum().sort_values(ascending=False).head(10)
                tp.index = [s[:35] + "…" if len(str(s)) > 35 else s for s in tp.index]
                fig6 = px.bar(tp[::-1], orientation="h",
                              labels={"value":"Units Sold","index":"Product"},
                              title="Top 10 Products by Units Sold",
                              color=tp[::-1].values,
                              color_continuous_scale="Oranges")
                fig6.update_layout(height=400, coloraxis_showscale=False)
                st.plotly_chart(fig6, use_container_width=True)

        # Panel 8 – API Catalog by Category
        with col_b:
            if "category" in df_p.columns:
                cat_c = df_p["category"].value_counts().head(12)
                fig7 = px.bar(cat_c[::-1], orientation="h",
                              labels={"value":"Product Count","index":"Category"},
                              title="API Catalog: Products by Category",
                              color=cat_c[::-1].values,
                              color_continuous_scale="YlOrBr")
                fig7.update_layout(height=400, coloraxis_showscale=False)
                st.plotly_chart(fig7, use_container_width=True)

        # Panel 5 – Unit Price Distribution
        price_col = None
        for c in ["unit_price_gbp", "unit_price", "price"]:
            if c in df_t.columns:
                price_col = c
                break
        if price_col:
            st.subheader("Unit Price Distribution")
            mean_p   = df_t[price_col].mean()
            median_p = df_t[price_col].median()
            fig8 = px.histogram(df_t[df_t[price_col] < df_t[price_col].quantile(0.99)],
                                x=price_col, nbins=60,
                                title="Unit Price Distribution (trimmed at 99th pct)",
                                labels={price_col:"Unit Price (£)"})
            fig8.add_vline(x=mean_p,   line_dash="dash",  line_color="red",
                           annotation_text=f"Mean £{mean_p:.2f}")
            fig8.add_vline(x=median_p, line_dash="dashdot", line_color="orange",
                           annotation_text=f"Median £{median_p:.2f}")
            fig8.update_layout(height=350)
            st.plotly_chart(fig8, use_container_width=True)
            st.caption("Strong right-skew: most items < £5. High-value outliers push mean above median.")

        # Product catalog table (if available)
        if df_p is not None and not df_p.empty:
            st.subheader("Product Catalog Explorer")
            cats = ["All"] + sorted(df_p["category"].dropna().unique().tolist()) if "category" in df_p.columns else ["All"]
            sel_cat = st.selectbox("Filter by Category", cats)
            show_df = df_p if sel_cat == "All" else df_p[df_p["category"] == sel_cat]
            disp_cols = [c for c in ["title","category","brand","price","rating","stock"] if c in show_df.columns]
            st.dataframe(show_df[disp_cols].reset_index(drop=True), use_container_width=True, height=300)

    # ── Tab 3 : Co-Purchase Graph ─────────────────────────────────────────────
    with tab3:
        st.subheader("Co-Purchase Community Detection (Neo4j)")

        if df_c is not None and not df_c.empty:
            col_g1, col_g2 = st.columns(2)

            # Panel 7 – Community Size Distribution
            with col_g1:
                size_col = "community_size" if "community_size" in df_c.columns else None
                if size_col:
                    sizes = df_c.drop_duplicates("community_id")[size_col] if "community_id" in df_c.columns else df_c[size_col]
                    sc = sizes.value_counts().sort_index().head(20).reset_index()
                    sc.columns = ["size", "count"]
                    median_s = sizes.median()
                    fig9 = px.bar(sc, x="size", y="count",
                                  title="Co-Purchase Community Size Distribution",
                                  labels={"size":"Community Size (# Products)","count":"# Communities"},
                                  color_discrete_sequence=["mediumpurple"])
                    fig9.add_vline(x=median_s, line_dash="dash", line_color="red",
                                   annotation_text=f"Median: {int(median_s)}")
                    fig9.update_layout(height=370)
                    st.plotly_chart(fig9, use_container_width=True)
                    st.caption("Most communities are size 2–4 (pair/trio purchases). Large communities (≥10) are rare bundle opportunities.")

            # Top communities table
            with col_g2:
                if "community_id" in df_c.columns and size_col:
                    top_comm = (
                        df_c.groupby("community_id")[size_col]
                        .first()
                        .sort_values(ascending=False)
                        .head(10)
                        .reset_index()
                    )
                    top_comm.columns = ["Community ID", "Size"]
                    st.subheader("Top 10 Largest Communities")
                    st.dataframe(top_comm, use_container_width=True, height=300)
                    st.caption("Large communities = strong bundle / cross-sell candidates.")

            # Raw community explorer
            st.subheader("Community Explorer")
            if "community_id" in df_c.columns:
                min_id = int(df_c["community_id"].min())
                max_id = int(df_c["community_id"].max())
                sel_id = st.number_input("Enter Community ID", min_value=min_id, max_value=max_id,
                                         value=min_id, step=1)
                comm_rows = df_c[df_c["community_id"] == sel_id]
                if not comm_rows.empty:
                    prod_ids = comm_rows["product_id"].tolist() if "product_id" in comm_rows.columns else []
                    st.write(f"**Community {sel_id}** — {len(prod_ids)} products")
                    st.write(", ".join(str(p) for p in prod_ids[:50]))
                    if len(prod_ids) > 50:
                        st.caption(f"…and {len(prod_ids) - 50} more.")
        else:
            st.info("Co-purchase data not available. Ensure `cleaned_copurchase.csv` is present.")

    # ── Tab 4 : Governance ───────────────────────────────────────────────────
    with tab4:
        st.subheader("🔒 Data Governance & Security")

        st.markdown("""
        ### Data Classification
        | Field | Sensitivity | Action |
        |---|---|---|
        | `customer_id` | 🔴 PII – Confidential | SHA-256 pseudonymised before sharing |
        | `invoice_no` | 🟠 Business Confidential | Finance & Analytics roles only |
        | `total_price_gbp` | 🟠 Business Confidential | Aggregate-only in dashboards |
        | `stock_code`, `description` | 🟡 Internal | Standard read access |
        | `country`, `invoice_date` | 🟡 Internal | Standard read access |
        | `product_id`, `category` (API) | 🟢 Public Reference | Freely queryable |
        | `community_id` (Neo4j) | 🟢 Public Reference | Freely queryable |
        """)

        st.markdown("""
        ### Role-Based Access Control
        | Role | Access Scope | PII? | Write? |
        |---|---|---|---|
        | Data Engineer | All tables + views | Pseudonymised | Yes |
        | Business Analyst | `transactions_anon` + products | No | No |
        | Reporting Dashboard | Aggregated views only | No | No |
        | External Auditor | Anonymised CSV exports | No | No |
        """)

        st.markdown("""
        ### Retention Policy
        | Asset | Retention | Backup |
        |---|---|---|
        | Transaction records | 7 years (UK Companies Act) | Daily `.sql` dump |
        | Product catalog | 1 year rolling | Weekly Atlas backup |
        | Co-purchase communities | Indefinite | Quarterly CSV export |
        | Dashboard exports | 90 days | Regenerable on demand |
        """)

        st.info("**GDPR Note:** Under Art. 5(1)(b), `customer_id` may only be used for the stated analytical purpose. Linkage to external PII requires fresh legal basis.")


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKETING DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def marketing_dashboard():
    st.title("📣 Marketing Analytics Dashboard")
    st.caption("Online Retail Dataset (Dec 2010 – Dec 2011) | Role: **Marketing** — Campaign View")

    # Focused KPIs
    total_rev  = df_t[REV].sum()
    total_cust = df_t["customer_id"].nunique() if "customer_id" in df_t.columns else 0
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Total Revenue",   f"£{total_rev:,.0f}")
    k2.metric("👤 Unique Customers", f"{total_cust:,}")
    if "is_guest" in df_t.columns:
        guest_rev_pct = df_t[df_t["is_guest"] == 1][REV].sum() / total_rev * 100
        k3.metric("🚪 Guest Revenue Share", f"{guest_rev_pct:.1f}%", help="Conversion opportunity")
    st.divider()

    # --- Section 1: Seasonality & Timing ---
    st.subheader("📅 Campaign Timing: When to Run Promotions")
    col1, col2 = st.columns(2)

    with col1:
        if "invoice_date" in df_t.columns:
            df_t["month"] = df_t["invoice_date"].dt.to_period("M").astype(str)
            monthly = df_t.groupby("month")[REV].sum().reset_index()
            monthly.columns = ["month", "revenue"]
            peak = monthly["revenue"].idxmax()
            colors = ["#e04c2f" if i == peak else "#4da8c7" for i in range(len(monthly))]
            fig = go.Figure(go.Bar(x=monthly["month"], y=monthly["revenue"],
                                   marker_color=colors,
                                   hovertemplate="£%{y:,.0f}<extra></extra>"))
            fig.update_layout(title="Monthly Revenue — Peak Campaign Opportunity",
                              xaxis_tickangle=-45, yaxis_tickformat="£,.0f", height=350)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("🔴 **Nov 2011 = peak.** Launch pre-holiday campaigns in October.")

    with col2:
        if "invoice_date" in df_t.columns:
            df_t["dow"] = df_t["invoice_date"].dt.day_name()
            order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            dow = df_t.groupby("dow")[REV].sum().reindex(order).reset_index()
            dow.columns = ["day", "revenue"]
            fig2 = px.bar(dow, x="day", y="revenue",
                          title="Revenue by Day — Best Days to Send Campaigns",
                          color="revenue", color_continuous_scale="Blues",
                          labels={"revenue":"Revenue (£)","day":""})
            fig2.update_layout(height=350, coloraxis_showscale=False, yaxis_tickformat="£,.0f")
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("📧 **Tuesday & Wednesday** yield highest revenue. Schedule email campaigns accordingly.")

    st.divider()

    # --- Section 2: Customer Segmentation ---
    st.subheader("🎯 Customer Segmentation for Targeted Campaigns")
    col3, col4 = st.columns(2)

    with col3:
        if "customer_id" in df_t.columns and "invoice_no" in df_t.columns:
            registered = df_t[df_t.get("is_guest", pd.Series(0, index=df_t.index)) != 1]
            seg_counts = registered.groupby("customer_id")["invoice_no"].nunique()
            def segment(n):
                if n == 1:   return "One-time"
                if n <= 5:   return "Occasional (2-5)"
                if n <= 15:  return "Regular (6-15)"
                return "Loyal (16+)"
            seg_df = seg_counts.apply(segment).value_counts().reset_index()
            seg_df.columns = ["Segment", "Count"]
            fig3 = px.pie(seg_df, names="Segment", values="Count",
                          title="Customer Segments — Re-engagement Targets",
                          color_discrete_sequence=px.colors.sequential.Blues_r)
            fig3.update_traces(textposition="inside", textinfo="percent+label")
            fig3.update_layout(height=370)
            st.plotly_chart(fig3, use_container_width=True)
            st.caption("💡 **One-time buyers** are the largest group — prime targets for re-engagement emails.")

    with col4:
        if "is_guest" in df_t.columns:
            grp = df_t.groupby("is_guest")[REV].sum().reset_index()
            grp["label"] = grp["is_guest"].map({0: "Registered", 1: "Guest"})
            grp["pct"] = (grp[REV] / grp[REV].sum() * 100).round(1)
            fig4 = px.bar(grp, x="label", y=REV,
                          color="label", color_discrete_map={"Registered":"steelblue","Guest":"coral"},
                          text=grp["pct"].astype(str) + "%",
                          title="Revenue by Customer Type — Registration Conversion ROI",
                          labels={REV:"Revenue (£)", "label":""})
            fig4.update_traces(textposition="inside", textfont_size=14)
            fig4.update_layout(showlegend=False, height=350, yaxis_tickformat="£,.0f")
            st.plotly_chart(fig4, use_container_width=True)
            st.caption("🔓 Converting guest buyers to registered accounts is a direct revenue growth lever.")

    st.divider()

    # --- Section 3: Top Products & Categories ---
    st.subheader("🛍️ Top Products & Categories for Campaign Selection")
    col5, col6 = st.columns(2)

    with col5:
        if "description" in df_t.columns and "quantity" in df_t.columns:
            tp = df_t.groupby("description")["quantity"].sum().sort_values(ascending=False).head(10)
            tp.index = [s[:35] + "…" if len(str(s)) > 35 else s for s in tp.index]
            fig5 = px.bar(tp[::-1], orientation="h",
                          title="Top 10 Bestsellers — Hero Campaign Products",
                          labels={"value":"Units Sold","index":"Product"},
                          color=tp[::-1].values, color_continuous_scale="Oranges")
            fig5.update_layout(height=400, coloraxis_showscale=False)
            st.plotly_chart(fig5, use_container_width=True)
            st.caption("🏆 Bestsellers are low-cost gift/novelty items. Feature them in seasonal campaigns.")

    with col6:
        if df_p is not None and "category" in df_p.columns:
            cat_c = df_p["category"].value_counts().head(12)
            fig6 = px.bar(cat_c[::-1], orientation="h",
                          title="Catalog Categories — Campaign Channel Planning",
                          labels={"value":"Product Count","index":"Category"},
                          color=cat_c[::-1].values, color_continuous_scale="YlOrBr")
            fig6.update_layout(height=400, coloraxis_showscale=False)
            st.plotly_chart(fig6, use_container_width=True)
            st.caption("📦 Electronics & Beauty have the widest product selection — ideal for catalogue campaigns.")

    st.divider()

    # --- Section 4: Geographic Focus ---
    st.subheader("🌍 Geographic Revenue — Market Prioritisation")
    if "country" in df_t.columns:
        top10 = df_t.groupby("country")[REV].sum().sort_values(ascending=False).head(10).reset_index()
        top10.columns = ["Country", "Revenue"]
        top10["Revenue Share %"] = (top10["Revenue"] / top10["Revenue"].sum() * 100).round(1)
        fig7 = px.bar(top10[::-1].reset_index(drop=True),
                      x="Revenue", y="Country", orientation="h",
                      title="Top 10 Revenue Markets",
                      color="Revenue", color_continuous_scale="Blues",
                      labels={"Revenue":"Revenue (£)"})
        fig7.update_layout(height=420, coloraxis_showscale=False, xaxis_tickformat="£,.0f")
        st.plotly_chart(fig7, use_container_width=True)
        with st.expander("Revenue by Country (Table)"):
            st.dataframe(top10, use_container_width=True)
        st.caption("🇬🇧 UK is dominant (>80%). **Germany, France, Ireland** are the top international growth markets for expansion campaigns.")

    st.divider()

    # --- Section 5: Co-Purchase Bundles ---
    st.subheader("🔗 Bundle & Cross-Sell Opportunities (Co-Purchase Data)")
    if df_c is not None and not df_c.empty and "community_size" in df_c.columns:
        size_col = "community_size"
        large = df_c[df_c[size_col] >= 5].drop_duplicates("community_id") if "community_id" in df_c.columns else pd.DataFrame()
        st.metric("🎁 Large Co-Purchase Bundles (≥5 products)", f"{len(large):,}",
                  help="Communities with 5+ products frequently bought together — strong bundle campaign candidates")
        if not large.empty:
            top_bundles = large.sort_values(size_col, ascending=False).head(10)[["community_id", size_col]]
            top_bundles.columns = ["Community ID", "Bundle Size"]
            st.dataframe(top_bundles, use_container_width=True)
            st.caption("💡 Use the largest bundles to design 'Frequently Bought Together' promotions or discount bundles.")
    else:
        st.info("Co-purchase data not available. Ensure `cleaned_copurchase.csv` is present.")


# ─── Route ────────────────────────────────────────────────────────────────────
if role == "Manager":
    manager_dashboard()
elif role == "Marketing":
    marketing_dashboard()
else:
    st.error(f"Unknown role: {role}")