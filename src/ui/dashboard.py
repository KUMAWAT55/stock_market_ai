import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.graph_objects as go


# DB Connection
engine = create_engine(
    "postgresql://market_admin:123456789@localhost/stock_market_ai"
)


st.set_page_config(
    page_title="AI Trading Dashboard",
    layout="wide"
)

st.title("📈 AI Trading System")

# ----------------------------------
# Sidebar
# ----------------------------------

@st.cache_data
def load_symbols():
    symbols_df = pd.read_sql(
        """
        SELECT symbol, name
        FROM symbols_master
        WHERE active = true
        ORDER BY symbol
        """,
        engine,
    )

    if not symbols_df.empty:
        return symbols_df

    fallback_df = pd.read_sql(
        """
        SELECT DISTINCT symbol, NULL AS name
        FROM market_data
        ORDER BY symbol
        """,
        engine,
    )
    return fallback_df


# ----------------------------------
# Load Data
# ----------------------------------

@st.cache_data
def load_prices(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_data
        WHERE symbol='{sym}'
        ORDER BY date
    """, engine)


@st.cache_data
def load_news(sym):

    return pd.read_sql(f"""
        SELECT *
        FROM market_news
        WHERE symbol='{sym.replace(".NS","")}'
        ORDER BY published_at DESC
        LIMIT 5
    """, engine)


# ----------------------------------
# Sidebar
# ----------------------------------

symbols_df = load_symbols()

if symbols_df.empty:
    st.warning("No symbols found in symbols_master or market_data.")
    st.stop()

symbol_labels = symbols_df.apply(
    lambda row: f"{row['symbol']} - {row['name']}" if pd.notna(row["name"]) and row["name"] else row["symbol"],
    axis=1,
).tolist()
label_to_symbol = dict(zip(symbol_labels, symbols_df["symbol"]))

selected_label = st.sidebar.selectbox(
    "Select Stock",
    symbol_labels,
)
symbol = label_to_symbol[selected_label]


# ----------------------------------
# Fetch
# ----------------------------------

prices = load_prices(symbol)
news = load_news(symbol)

# ----------------------------------
# Layout
# ----------------------------------

col1, col2 = st.columns([3, 1])

# ----------------------------------
# Chart
# ----------------------------------

with col1:

    st.subheader(f"{symbol} Price Chart")

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=prices["date"],
        open=prices["open"],
        high=prices["high"],
        low=prices["low"],
        close=prices["close"],
        name="Price"
    ))

    st.plotly_chart(fig, use_container_width=True)




# ----------------------------------
# News Section
# ----------------------------------

st.subheader("📰 Latest News")

if not news.empty:

    for _, row in news.iterrows():

        sentiment = (row.get("sentiment_label") or "neutral").lower()
        score = row.get("sentiment_score")
        color_map = {
            "positive": "green",
            "negative": "red",
            "neutral": "gray",
        }
        color = color_map.get(sentiment, "gray")
        score_text = f"{float(score):.2f}" if pd.notna(score) else "0.00"

        st.markdown(
            f"""
            **{row['title']}**  
            Source: {row['source']}  
            Sentiment: :{color}[{sentiment.title()} ({score_text})]  
            [Read More]({row['url']})
            """
        )

else:
    st.info("No recent news")
