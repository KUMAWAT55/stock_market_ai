-- MASTER SYMBOL TABLE: Stores all tradable symbols and their metadata
DROP TABLE IF EXISTS symbols_master;

CREATE TABLE symbols_master (
    id SERIAL PRIMARY KEY,                 -- Unique identifier for each symbol
    symbol TEXT UNIQUE NOT NULL,           -- Ticker symbol (must be unique)
    name TEXT,                             -- Full name of the security
    exchange TEXT,                         -- Exchange where listed (e.g., NSE, BSE)
    series TEXT,                           -- Series type (e.g., EQ, BE)
    date_of_listing TEXT,                  -- Listing date (format as string)
    paid_up_value TEXT,                    -- Paid-up value per share
    market_lot TEXT,                       -- Market lot size
    isin_number TEXT,                      -- International Securities Identification Number
    face_value TEXT,                       -- Face value per share
    active BOOLEAN DEFAULT TRUE,           -- Whether the symbol is currently active
    created_at TIMESTAMP DEFAULT NOW()     -- Record creation timestamp
);

-- MARKET DATA TABLE: Stores daily price, volume, and fundamental data for each symbol
DROP TABLE IF EXISTS market_data;
CREATE TABLE market_data (
    id SERIAL PRIMARY KEY,                 -- Unique identifier for each record

    symbol TEXT NOT NULL,                  -- Ticker symbol (foreign key to symbols_master.symbol)
    date DATE NOT NULL,                    -- Trading date
    source TEXT NOT NULL,                  -- Data source (e.g., NSE, Yahoo)

    -- Prices
    open FLOAT,                            -- Opening price
    high FLOAT,                            -- Highest price
    low FLOAT,                             -- Lowest price
    close FLOAT,                           -- Closing price
    adj_close FLOAT,                       -- Adjusted closing price

    -- Volume
    volume BIGINT,                         -- Number of shares traded
    traded_value FLOAT,                    -- Total traded value
    vwap FLOAT,                            -- Volume Weighted Average Price

    -- Corporate actions
    dividend FLOAT,                        -- Dividend per share
    split FLOAT,                           -- Split ratio

    -- Fundamentals
    market_cap BIGINT,                     -- Market capitalization
    pe_ratio FLOAT,                        -- Price-to-Earnings ratio
    eps FLOAT,                             -- Earnings per share
    book_value FLOAT,                      -- Book value per share
    dividend_yield FLOAT,                  -- Dividend yield percentage
    beta FLOAT,                            -- Beta value (volatility measure)

    -- Meta information
    sector TEXT,                           -- Sector classification
    industry TEXT,                         -- Industry classification
    exchange TEXT,                         -- Exchange name (redundant for denormalization)
    currency TEXT,                         -- Trading currency

    created_at TIMESTAMP DEFAULT NOW(),    -- Record creation timestamp

    UNIQUE(symbol, date, source)           -- Prevent duplicate records for the same symbol, date, and source
);

-- MARKET NEWS TABLE: Stores news articles related to market symbols
CREATE TABLE IF NOT EXISTS market_news (
    id BIGSERIAL PRIMARY KEY,              -- Unique identifier for each news article

    symbol VARCHAR(30) NOT NULL,           -- Ticker symbol the news relates to

    title TEXT NOT NULL,                   -- News headline/title

    summary TEXT,                          -- Short summary of the news

    url TEXT NOT NULL,                     -- URL to the news article

    source VARCHAR(50),                    -- News source/publisher

    published_at TIMESTAMP WITHOUT TIME ZONE, -- When the news was published
    sentiment_score FLOAT DEFAULT 0.0,     -- Sentiment score in range [-1, 1]
    sentiment_label VARCHAR(20) DEFAULT 'neutral', -- Sentiment class

    created_at TIMESTAMP WITHOUT TIME ZONE     -- Record creation timestamp
        DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate news articles by URL
    CONSTRAINT uq_market_news_url UNIQUE (url)
);

-- STOCK PREDICTIONS TABLE: Stores ML model predictions per symbol/date
CREATE TABLE IF NOT EXISTS stock_predictions (
    id BIGSERIAL PRIMARY KEY,

    symbol VARCHAR(30) NOT NULL,
    prediction_date DATE NOT NULL,
    target_date DATE NOT NULL,

    predicted_return FLOAT,
    predicted_close FLOAT,
    direction VARCHAR(20),

    model_name VARCHAR(50) NOT NULL DEFAULT 'random_forest_v1',
    train_rows INT,
    r2_score FLOAT,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- MODEL BACKTEST RESULTS TABLE: Stores model-wise walk-forward evaluation metrics
CREATE TABLE IF NOT EXISTS model_backtest_results (
    id BIGSERIAL PRIMARY KEY,

    symbol VARCHAR(30) NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    run_date DATE NOT NULL,

    sample_count INT,
    directional_accuracy FLOAT,
    mae FLOAT,
    rmse FLOAT,
    avg_true_return FLOAT,
    avg_pred_return FLOAT,
    cumulative_return FLOAT,
    strategy_return FLOAT,

    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
