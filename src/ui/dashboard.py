import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.graph_objects as go
import re


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

stocks = ["20MICRONS", "360ONE", "3IINFOLTD"]

symbol = st.sidebar.selectbox(
    "Select Stock",
    stocks
)

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

        color = "green" if re.search("Fund",row["title"])  else "red"

        st.markdown(
            f"""
            **{row['title']}**  
            Source: {row['source']}  
            Sentiment: :{color}[{row["title"]}]  
            [Read More]({row['url']})
            """
        )

else:
    st.info("No recent news")
