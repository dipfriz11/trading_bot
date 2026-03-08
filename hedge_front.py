import streamlit as st
st.set_page_config(layout="centered")
import pandas as pd
import numpy as np
from dataclasses import dataclass
import plotly.graph_objects as go

@dataclass
class Position:
    size: float
    avg_price: float

def add_order(position, add_size, price):
    total_value = position.size * position.avg_price
    total_value += add_size * price
    new_size = position.size + add_size
    new_avg = total_value / new_size
    return Position(new_size, new_avg)

def calc_profit_price(long, short, target=1.0):
    A = long.size - short.size
    B = short.size * short.avg_price - long.size * long.avg_price
    if A == 0:
        return None
    return (target - B) / A

st.markdown("""
<style>
.long-label {
    color: #16c784;
    font-weight: 700;
    margin-bottom: 4px;
}
.short-label {
    color: #ea3943;
    font-weight: 700;
    margin-bottom: 4px;
}
.signal-long {
    color: #16c784;
    font-weight: 700;
    margin-top: 6px;
}
.signal-short {
    color: #ea3943;
    font-weight: 700;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

st.title("Hedge Strategy Calculator")

st.sidebar.header("Config")

st.sidebar.markdown('<div class="long-label">Start LONG size</div>', unsafe_allow_html=True)
start_long_size = st.sidebar.number_input(
    "Start LONG size",
    value=6.0,
    label_visibility="collapsed"
)

st.sidebar.markdown('<div class="long-label">Start LONG price</div>', unsafe_allow_html=True)
start_long_price = st.sidebar.number_input(
    "Start LONG price",
    value=1.85,
    step=0.00000001,
    format="%.8f",
    label_visibility="collapsed"
)

st.sidebar.markdown('<div class="short-label">Start SHORT size</div>', unsafe_allow_html=True)
start_short_size = st.sidebar.number_input(
    "Start SHORT size",
    value=12.0,
    label_visibility="collapsed"
)

st.sidebar.markdown('<div class="short-label">Start SHORT price</div>', unsafe_allow_html=True)
start_short_price = st.sidebar.number_input(
    "Start SHORT price",
    value=1.85,
    step=0.00000001,
    format="%.8f",
    label_visibility="collapsed"
)

main_input = st.sidebar.text_input(
    "Main multipliers (через запятую)",
    value="2,3"
)

opp_input = st.sidebar.text_input(
    "Opp multipliers (через запятую)",
    value="0.25,0.5,0.75"
)
target_profit = st.sidebar.number_input("Target profit", value=1.0)

start_balance = st.sidebar.number_input(
    "Start Balance ($)",
    value=100.0
)

leverage = st.sidebar.number_input(
    "Leverage",
    value=10
)


def parse_input(text):
    return [float(x.strip()) for x in text.split(",") if x.strip()]

main_multipliers = parse_input(main_input)
opp_multipliers = parse_input(opp_input)

st.subheader("Signals (вводи по одному)")
signal_type = st.selectbox("Signal type", ["LONG", "SHORT"])

if signal_type == "LONG":
    st.markdown('<div class="signal-long">Current signal: LONG</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="signal-short">Current signal: SHORT</div>', unsafe_allow_html=True)

signal_price = st.number_input(
    "Signal price",
    value=1.9,
    step=0.00000001,
    format="%.8f"
)

if "history" not in st.session_state:
    st.session_state.history = []

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Add Signal"):
        st.session_state.history.append((signal_type, signal_price))

with col2:
    if st.button("Undo Last Signal"):
        if st.session_state.history:
            st.session_state.history.pop()

with col3:
    if st.button("Reset Simulation"):
        st.session_state.history = []

# Конвертируем USDT → количество монет
long_qty = start_long_size / start_long_price if start_long_price != 0 else 0
short_qty = start_short_size / start_short_price if start_short_price != 0 else 0

long = Position(long_qty, start_long_price)
short = Position(short_qty, start_short_price)


st.subheader("Multi-config Simulation")

current_price = start_long_price

if st.session_state.history:
    current_price = st.session_state.history[-1][1]

heatmap_data = []

for m in main_multipliers:
    for o in opp_multipliers:

        long = Position(long_qty, start_long_price)
        short = Position(short_qty, start_short_price)

        step = 0
        rows = []

        target = calc_profit_price(long, short, target_profit)

        percent = None
        if target:
            percent = (target - current_price) / current_price * 100

        position_notional = (
            abs(long.size * long.avg_price) +
            abs(short.size * short.avg_price)
        )

        used_margin = round(position_notional / leverage, 4)
        margin_load = round((used_margin / start_balance) * 100, 2)

        if margin_load < 10:
            risk = "SAFE"
        elif margin_load < 20:
            risk = "NORMAL"
        elif margin_load < 30:
            risk = "RISK"
        elif margin_load <= 40:
            risk = "DANGER"
        else:
            risk = "MARGIN RISK"

        rows.append({
            "L_size": long.size,
            "L_avg": long.avg_price,
            "S_size": short.size,
            "S_avg": short.avg_price,
            "price": current_price,
            "target": target,
            "% to target": percent,
            
        })

        for signal, price in st.session_state.history:
            step += 1
            current_price = price

            if signal == "LONG":
                long = add_order(long, long.size * m, price)
                short = add_order(short, short.size * o, price)
            else:
                short = add_order(short, short.size * m, price)
                long = add_order(long, long.size * o, price)

            target = calc_profit_price(long, short, target_profit)

            percent = None
            if target:
                percent = (target - current_price) / current_price * 100
                percent = round(percent, 4)

            position_notional = (
                abs(long.size * long.avg_price) +
                abs(short.size * short.avg_price)
            )

            used_margin = round(position_notional / leverage, 4)
            margin_load = round((used_margin / start_balance) * 100, 2)

            if margin_load < 10:
                risk = "SAFE"
            elif margin_load < 20:
                risk = "NORMAL"
            elif margin_load < 30:
                risk = "RISK"
            elif margin_load <= 40:
                risk = "DANGER"
            else:
                risk = "MARGIN RISK"

            rows.append({
                "L_size": long.size,
                "L_avg": long.avg_price,
                "S_size": short.size,
                "S_avg": short.avg_price,
                "price": current_price,
                "target": target,
                "% to target": percent,
                
            })

        df = pd.DataFrame(rows)

        max_margin_load = margin_load

        if max_margin_load < 10:
            strategy_risk = "SAFE"
        elif max_margin_load < 20:
            strategy_risk = "NORMAL"
        elif max_margin_load < 30:
            strategy_risk = "RISK"
        elif max_margin_load <= 40:
            strategy_risk = "DANGER"
        else:
            strategy_risk = "MARGIN RISK"

        st.markdown(f"### Config: main={m} | opp={o}")
        st.markdown(f"Max Margin Load: **{round(max_margin_load,2)}%**")
        st.markdown(f"Used Margin: **{round(used_margin,2)} USDT**")
        if strategy_risk == "SAFE":
            st.success(f"Strategy Risk: {strategy_risk}")
        elif strategy_risk == "NORMAL":
            st.info(f"Strategy Risk: {strategy_risk}")
        elif strategy_risk == "RISK":
            st.warning(f"Strategy Risk: {strategy_risk}")
        else:
            st.error(f"Strategy Risk: {strategy_risk}")

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "price": st.column_config.NumberColumn(
                    "price",
                    format="%.8f",
                ),
                "target": st.column_config.NumberColumn(
                    "target",
                    format="%.8f",
                ),
                "% to target": st.column_config.NumberColumn(
                    "% to T",
                    format="%.2f",
                ),
                "long_size": st.column_config.NumberColumn(
                    "long_size",
                    format="%.4f",
                ),
                "short_size": st.column_config.NumberColumn(
                    "short_size",
                    format="%.4f",
                ),
                "L_avg": st.column_config.NumberColumn(
                    "L_avg",
                    format="%.8f",
                ),

                "S_avg": st.column_config.NumberColumn(
                    "S_avg",
                    format="%.8f",
                ),
            }
        )

        last_percent = df["% to target"].iloc[-1]

        heatmap_data.append({
            "main": m,
            "opp": o,
            "percent_to_target": last_percent
        })

        # ---- Strategy chart ----

        fig = go.Figure()

        # ---------- PROFIT CURVE ----------

        price_range = np.linspace(
            min(df["price"]) * 0.95,
            max(df["price"]) * 1.05,
            100
        )

        profits = []

        for p in price_range:

            long_pnl = long.size * (p - long.avg_price)
            short_pnl = short.size * (short.avg_price - p)

            profits.append(long_pnl + short_pnl)

        profit_fig = go.Figure()

        profit_fig.add_trace(go.Scatter(
            x=price_range,
            y=profits,
            mode="lines",
            name="Strategy Profit"
        ))

        profit_fig.update_layout(
            title="Profit Curve",
            xaxis_title="Price",
            yaxis_title="Profit"
        )

        # линия break-even
        profit_fig.add_hline(
             y=0,
            line_dash="dash",
            line_color="gray"
        )

        # текущая цена
        current_price = df["price"].iloc[-1]

        profit_fig.add_vline(
            x=current_price,
            line_dash="dot",
            line_color="yellow"
        )

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["price"],
            mode="lines+markers",
            name="Price"
        ))

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["L_avg"],
            mode="lines",
            name="LONG avg"
        ))

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["S_avg"],
            mode="lines",
            name="SHORT avg"
        ))

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["target"],
            mode="lines",
            name="Target"
        ))

        fig.update_layout(
            height=350,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=30, b=10)
        )

        with st.expander("Show chart"):
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{m}_{o}")

        with st.expander("Show profit curve"):
            st.plotly_chart(profit_fig, use_container_width=True, key=f"profit_{m}_{o}")

# -------- Heatmap of configs --------

st.markdown("## Config Efficiency Heatmap")

heat_df = pd.DataFrame(heatmap_data)

pivot = heat_df.pivot(
    index="main",
    columns="opp",
    values="percent_to_target"
)

heatmap_fig = go.Figure(
    data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="RdYlGn_r",
        text=pivot.values,
        texttemplate="%{text:.2f}%",
        textfont={"size":14},
        colorbar=dict(title="% to target")
    )
)

heatmap_fig.update_layout(
    xaxis_title="Opp multiplier",
    yaxis_title="Main multiplier",
)

st.plotly_chart(heatmap_fig, use_container_width=True)