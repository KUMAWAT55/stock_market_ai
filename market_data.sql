
-- MASTER SYMBOL TABLE
DROP TABLE IF EXISTS symbols_master;

CREATE TABLE symbols_master (

    id SERIAL PRIMARY KEY,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    exchange TEXT,
    series TEXT,
    date_of_listing TEXT,
    paid_up_value TEXT,
    market_lot TEXT,
    isin_number TEXT,
    face_value TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- MARKET DATA TABLE
DROP TABLE IF EXISTS market_data;
CREATE TABLE market_data (

    id SERIAL PRIMARY KEY,

    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    source TEXT NOT NULL,

    -- Prices
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    adj_close FLOAT,

    -- Volume
    volume BIGINT,
    traded_value FLOAT,
    vwap FLOAT,

    -- Corporate
    dividend FLOAT,
    split FLOAT,

    -- Fundamentals
    market_cap BIGINT,
    pe_ratio FLOAT,
    eps FLOAT,
    book_value FLOAT,
    dividend_yield FLOAT,
    beta FLOAT,

    -- Meta
    sector TEXT,
    industry TEXT,
    exchange TEXT,
    currency TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(symbol, date, source)
);


CREATE TABLE IF NOT EXISTS market_news (

    id BIGSERIAL PRIMARY KEY,

    symbol VARCHAR(30) NOT NULL,

    title TEXT NOT NULL,

    summary TEXT,

    url TEXT NOT NULL,

    source VARCHAR(50),

    published_at TIMESTAMP WITHOUT TIME ZONE,

    created_at TIMESTAMP WITHOUT TIME ZONE
        DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate news
    CONSTRAINT uq_market_news_url UNIQUE (url)
);

