"""
Operator Dashboard — Systematic Trading Signal & Risk API
4 pages: Signal Monitor | Portfolio Risk | Anomaly Feed | System Health
"""
import os

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Trading Signal Dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{API_BASE_URL}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Could not reach API: {e}")
        return None


def post(path: str, json: dict | None = None) -> dict | None:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{API_BASE_URL}{path}", json=json)
            resp.raise_for_status()
            if resp.status_code == 204:
                return {}
            return resp.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Could not reach API: {e}")
        return None


def delete(path: str) -> bool:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(f"{API_BASE_URL}{path}")
            resp.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
        return False
    except Exception as e:
        st.error(f"Could not reach API: {e}")
        return False


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

page = st.sidebar.selectbox(
    "Navigate",
    ["Signal Monitor", "Technical Indicators", "Portfolio Risk", "Anomaly Feed", "Webhooks", "System Health"],
)

# ---------------------------------------------------------------------------
# Page 1 — Signal Monitor
# ---------------------------------------------------------------------------

if page == "Signal Monitor":
    st.title("Signal Monitor")
    st.caption("Generate a BUY / SELL / HOLD signal for any symbol and review history.")

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", value="AAPL").upper()
    with col2:
        provider = st.selectbox("Provider", ["finnhub", "alphavantage", "binance"])
    with col3:
        strategy = st.selectbox("Strategy", ["trend-following", "mean-reversion", "caution"])

    if st.button("Generate Signal"):
        data = get(f"/signals/{symbol}", params={"provider": provider, "strategy": strategy})
        if data:
            signal = data["signal"]
            color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(signal, "gray")
            st.markdown(f"<h2 style='color:{color}'>{signal}</h2>", unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Confidence", f"{data['confidence']:.1%}")
            m2.metric("Weighted Score", f"{data['weighted_score']:.3f}")
            m3.metric("RSI", f"{data['rsi']:.1f}" if data.get("rsi") else "N/A")
            m4.metric("ADX", f"{data['adx']:.1f}" if data.get("adx") else "N/A")

    st.divider()
    st.subheader("Signal History")
    limit = st.slider("Records", min_value=5, max_value=100, value=20)
    history = get(f"/signals/{symbol}/history", params={"provider": provider, "strategy": strategy, "limit": limit})
    if history:
        st.dataframe(
            [
                {
                    "Time": r["timestamp"],
                    "Signal": r["signal"],
                    "Confidence": f"{r['confidence']:.1%}",
                    "Score": f"{r['weighted_score']:.3f}",
                    "Strategy": r["strategy_mode"],
                    "Price": r["price"],
                    "RSI": r.get("rsi"),
                    "ADX": r.get("adx"),
                }
                for r in history
            ],
            use_container_width=True,
        )

    st.divider()
    st.subheader("Price History")
    prices = get("/prices/history", params={"symbol": symbol, "provider": provider, "limit": 100})
    if prices:
        st.line_chart(
            data={r["timestamp"]: r["price"] for r in prices},
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Page 2 — Technical Indicators
# ---------------------------------------------------------------------------

elif page == "Technical Indicators":
    st.title("Technical Indicators")
    st.caption("Full indicator suite: RSI, MACD, Bollinger Bands, EMA, SMA, ADX, OBV.")

    col1, col2, col3 = st.columns(3)
    with col1:
        ti_symbol = st.text_input("Symbol", value="AAPL", key="ti_symbol").upper()
    with col2:
        ti_provider = st.selectbox("Provider", ["finnhub", "alphavantage", "binance"], key="ti_provider")
    with col3:
        ti_strategy = st.selectbox("Strategy", ["trend-following", "mean-reversion", "caution"], key="ti_strategy")

    if st.button("Compute Indicators"):
        data = get(
            f"/analytics/{ti_symbol}/indicators",
            params={"provider": ti_provider, "strategy": ti_strategy},
        )
        if data:
            signal = data["signal"]
            color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(signal, "gray")
            st.markdown(f"<h3 style='color:{color}'>Signal: {signal} — Confidence: {data['confidence']:.1%}</h3>", unsafe_allow_html=True)
            st.caption(f"Based on {data['price_count']} price points")

            st.divider()
            st.subheader("Momentum")
            m1, m2, m3 = st.columns(3)
            m1.metric("RSI (14)", f"{data['rsi']:.2f}" if data.get("rsi") else "N/A",
                      help="<30 oversold, >70 overbought")
            m2.metric("EMA (20)", f"{data['ema']:.4f}" if data.get("ema") else "N/A")
            m3.metric("SMA (20)", f"{data['sma']:.4f}" if data.get("sma") else "N/A")

            st.subheader("Trend Strength")
            t1, t2 = st.columns(2)
            t1.metric("ADX (14)", f"{data['adx']:.2f}" if data.get("adx") else "N/A",
                      help=">25 strong trend, <20 weak/ranging")
            t2.metric("OBV", f"{data['obv']:,.0f}" if data.get("obv") else "N/A",
                      help="Rising OBV = volume confirms price move")

            if data.get("macd"):
                st.subheader("MACD")
                macd = data["macd"]
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("MACD Line", f"{macd['line']:.4f}")
                mc2.metric("Signal Line", f"{macd['signal']:.4f}")
                hist_val = macd["histogram"]
                mc3.metric("Histogram", f"{hist_val:.4f}",
                           delta=f"{'bullish' if hist_val > 0 else 'bearish'}")

            if data.get("bollinger"):
                st.subheader("Bollinger Bands")
                bb = data["bollinger"]
                bc1, bc2, bc3, bc4 = st.columns(4)
                bc1.metric("Upper", f"{bb['upper']:.4f}")
                bc2.metric("Middle", f"{bb['middle']:.4f}")
                bc3.metric("Lower", f"{bb['lower']:.4f}")
                bc4.metric("Bandwidth", f"{bb['bandwidth']:.4f}")

            if data.get("reasons"):
                st.subheader("Signal Reasons")
                for reason in data["reasons"]:
                    st.markdown(f"- {reason}")

# ---------------------------------------------------------------------------
# Page 3 — Portfolio Risk
# ---------------------------------------------------------------------------

elif page == "Portfolio Risk":
    st.title("Portfolio Risk")
    st.caption("Manage portfolios, add positions, view live P&L, and compute risk metrics.")

    # ---- Create portfolio ----
    with st.expander("Create New Portfolio"):
        with st.form("create_portfolio_form"):
            p_name = st.text_input("Portfolio Name")
            p_type = st.selectbox("Type", ["stock", "crypto", "mixed"])
            submitted = st.form_submit_button("Create")
            if submitted and p_name:
                result = post("/portfolios", json={"name": p_name, "portfolio_type": p_type})
                if result:
                    st.success(f"Created portfolio '{p_name}' — ID: {result['id']}")
                    st.rerun()

    st.divider()

    # ---- Load portfolios ----
    portfolios = get("/portfolios")
    if not portfolios:
        st.info("No portfolios yet. Create one above.")
        st.stop()

    portfolio_map = {p["name"]: p["id"] for p in portfolios}
    selected_name = st.selectbox("Select Portfolio", list(portfolio_map.keys()))
    portfolio_id = portfolio_map[selected_name]

    # ---- Add position ----
    with st.expander("Add Position"):
        st.markdown("**Check Live Price**")
        lp_col1, lp_col2, lp_col3 = st.columns([2, 2, 1])
        with lp_col1:
            lp_symbol = st.text_input("Symbol to check", value="AAPL", key="lp_symbol").upper()
        with lp_col2:
            lp_provider = st.selectbox("Provider", ["finnhub", "alphavantage", "binance"], key="lp_provider")
        with lp_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Fetch Price"):
                price_data = get("/prices/latest", params={"symbol": lp_symbol, "provider": lp_provider})
                if price_data:
                    st.success(f"**{lp_symbol}** — `${price_data['price']:,.4f}` via {lp_provider}")

        st.divider()
        with st.form("add_position_form"):
            col1, col2 = st.columns(2)
            with col1:
                pos_symbol = st.text_input("Symbol", value="AAPL").upper()
                pos_quantity = st.number_input("Quantity", min_value=0.01, value=10.0, step=1.0)
            with col2:
                pos_price = st.number_input("Purchase Price", min_value=0.01, value=100.0, step=1.0)
                pos_provider = st.selectbox("Provider", ["finnhub", "alphavantage", "binance"])
            add_submitted = st.form_submit_button("Add Position")
            if add_submitted:
                result = post(
                    f"/portfolios/{portfolio_id}/positions",
                    json={
                        "symbol": pos_symbol,
                        "quantity": pos_quantity,
                        "price": pos_price,
                        "provider": pos_provider,
                    },
                )
                if result:
                    st.success(f"Added {pos_quantity} x {pos_symbol} at ${pos_price:.2f}")
                    st.rerun()

    st.divider()

    # ---- Portfolio snapshot ----
    st.subheader("Live Snapshot")
    snapshot = get(f"/portfolios/{portfolio_id}/snapshot")
    if snapshot and snapshot.get("positions"):
        m1, m2 = st.columns(2)
        m1.metric("Total Value", f"${snapshot['total_value']:,.2f}")
        m2.metric("Unrealized P&L", f"${snapshot['total_pnl']:,.2f}")

        for pos in snapshot["positions"]:
            pnl_color = "green" if pos["unrealized_pnl"] >= 0 else "red"
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 2, 1])
                c1.markdown(f"**{pos['symbol']}** (`{pos['provider']}`)")
                c2.metric("Qty", pos["quantity"])
                c3.metric("Avg Cost", f"${pos['avg_cost_basis']:.2f}")
                c4.markdown(
                    f"Current: `${pos['current_price']:.2f}` | "
                    f"<span style='color:{pnl_color}'>P&L: ${pos['unrealized_pnl']:,.2f} ({pos['pnl_pct']:.1%})</span>",
                    unsafe_allow_html=True,
                )
                if c5.button("Close", key=f"close_{pos['position_id']}"):
                    if delete(f"/portfolios/{portfolio_id}/positions/{pos['position_id']}"):
                        st.success(f"Closed {pos['symbol']}")
                        st.rerun()
    else:
        st.info("No active positions in this portfolio.")

    st.divider()

    # ---- Risk metrics ----
    st.subheader("Risk Metrics")
    if st.button("Compute Risk"):
        data = get(f"/analytics/portfolios/{portfolio_id}/risk")
        if data:
            if data.get("warning"):
                st.warning(data["warning"])
            else:
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Value", f"${data['total_value']:,.2f}")
                m2.metric("VaR (1-day 95%)", f"${data['var_1day_95']:,.2f}" if data.get("var_1day_95") else "N/A")
                m3.metric("Sharpe Ratio", f"{data['sharpe_ratio']:.3f}" if data.get("sharpe_ratio") else "N/A")
                m4.metric("Max Drawdown", f"{data['max_drawdown']:.1%}" if data.get("max_drawdown") else "N/A")
                m5.metric("Rolling Vol", f"{data['rolling_volatility']:.1%}" if data.get("rolling_volatility") else "N/A")

                if data.get("breaches"):
                    st.error(f"Threshold breaches: {', '.join(data['breaches'])}")
                else:
                    st.success("No threshold breaches.")

                if data.get("correlation_matrix"):
                    st.subheader("Correlation Matrix")
                    st.dataframe(data["correlation_matrix"], use_container_width=True)

    st.divider()

    # ---- Delete portfolio ----
    with st.expander("Danger Zone"):
        st.warning(f"This will permanently delete '{selected_name}' and all its positions.")
        if st.button("Delete Portfolio", type="primary"):
            if delete(f"/portfolios/{portfolio_id}"):
                st.success(f"Deleted portfolio '{selected_name}'")
                st.rerun()

# ---------------------------------------------------------------------------
# Page 3 — Anomaly Feed
# ---------------------------------------------------------------------------

elif page == "Anomaly Feed":
    st.title("Anomaly Feed")
    st.caption("Live unresolved alerts from the anomaly detector and risk engine.")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Refresh"):
            st.rerun()

    symbol_filter = st.text_input("Filter by symbol (leave blank for all)")
    params = {"limit": 100}
    if symbol_filter:
        params["symbol"] = symbol_filter.upper()

    alerts = get("/alerts/active", params=params)
    if not alerts:
        st.info("No active alerts.")
    else:
        severity_color = {"high": "red", "medium": "orange", "low": "yellow"}
        for alert in alerts:
            severity = alert.get("severity", "low")
            color = severity_color.get(severity, "gray")
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 2, 1])
                c1.markdown(f"**{alert['symbol']}** — `{alert['anomaly_type']}`")
                c2.markdown(f"Provider: `{alert['provider']}`")
                c3.markdown(f":{color}[**{severity.upper()}**]")
                c4.markdown(f"Price: `${alert['price']:,.2f}` | {alert['timestamp'][:19]}")
                if c5.button("Resolve", key=alert["id"]):
                    result = post(f"/alerts/{alert['id']}/resolve")
                    if result is not None:
                        st.success(f"Resolved alert {alert['id'][:8]}...")
                        st.rerun()

# ---------------------------------------------------------------------------
# Page 5 — Webhooks
# ---------------------------------------------------------------------------

elif page == "Webhooks":
    st.title("Webhook Management")
    st.caption("Register endpoints to receive alert notifications when anomalies or risk breaches occur.")

    # ---- Register webhook ----
    with st.expander("Register New Webhook"):
        with st.form("register_webhook_form"):
            wh_url = st.text_input("Target URL", placeholder="https://your-endpoint.com/webhook")
            wh_col1, wh_col2 = st.columns(2)
            with wh_col1:
                wh_symbol = st.text_input("Symbol filter (leave blank for all)")
                wh_secret = st.text_input("Secret (optional, for HMAC signing)", type="password")
            with wh_col2:
                wh_min_severity = st.selectbox("Minimum severity", ["(all)", "low", "medium", "high"])
                wh_event_type = st.selectbox("Event type", ["alert.created"])
            wh_submitted = st.form_submit_button("Register")
            if wh_submitted and wh_url:
                payload = {"url": wh_url, "event_type": wh_event_type}
                if wh_symbol:
                    payload["symbol"] = wh_symbol.upper()
                if wh_min_severity != "(all)":
                    payload["min_severity"] = wh_min_severity
                if wh_secret:
                    payload["secret"] = wh_secret
                result = post("/webhooks", json=payload)
                if result:
                    st.success(f"Registered webhook — ID: {result['id']}")
                    st.rerun()

    st.divider()

    # ---- List webhooks ----
    st.subheader("Registered Webhooks")
    if st.button("Refresh", key="wh_refresh"):
        st.rerun()

    webhooks = get("/webhooks")
    if not webhooks:
        st.info("No webhooks registered.")
    else:
        for wh in webhooks:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                c1.markdown(f"`{wh['url']}`")
                c2.markdown(f"Symbol: `{wh['symbol'] or 'all'}` | Min severity: `{wh['min_severity'] or 'all'}`")
                c3.markdown(f"Event: `{wh['event_type']}` | Active: `{wh['is_active']}`")
                if c4.button("Delete", key=f"del_wh_{wh['id']}"):
                    if delete(f"/webhooks/{wh['id']}"):
                        st.success("Webhook deleted")
                        st.rerun()

# ---------------------------------------------------------------------------
# Page 6 — System Health
# ---------------------------------------------------------------------------

elif page == "System Health":
    st.title("System Health")
    st.caption("Live status of API dependencies.")

    if st.button("Refresh"):
        st.rerun()

    data = get("/health")
    if data:
        overall = data.get("status", "unknown")
        checks = data.get("checks", {})

        if overall == "ok":
            st.success("All systems operational")
        else:
            st.error("System degraded — check below")

        st.subheader("Service Checks")
        for service, status_val in checks.items():
            icon = "green" if status_val == "ok" else "red"
            st.markdown(f":{icon}[**{service.upper()}**] — `{status_val}`")

        st.subheader("API Base URL")
        st.code(API_BASE_URL)

    st.divider()
    st.subheader("Price Polling Jobs")
    st.caption("Start background polling to continuously ingest prices for symbols.")

    with st.expander("Start Polling Job"):
        with st.form("poll_form"):
            poll_col1, poll_col2, poll_col3 = st.columns(3)
            with poll_col1:
                poll_symbols = st.text_input("Symbols (comma-separated)", value="AAPL,TSLA")
            with poll_col2:
                poll_provider = st.selectbox("Provider", ["finnhub", "alphavantage", "binance"])
            with poll_col3:
                poll_interval = st.number_input("Interval (seconds)", min_value=10, value=30, step=10)
            poll_submitted = st.form_submit_button("Start Polling")
            if poll_submitted and poll_symbols:
                symbols_list = [s.strip().upper() for s in poll_symbols.split(",") if s.strip()]
                result = post("/prices/poll", json={
                    "symbols": symbols_list,
                    "provider": poll_provider,
                    "interval": poll_interval,
                })
                if result:
                    st.success(f"Polling started for {symbols_list}")
