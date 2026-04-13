CREATE TABLE IF NOT EXISTS silver_market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    series_layer VARCHAR(20) NOT NULL DEFAULT 'raw',
    price_timestamp TIMESTAMP NOT NULL,
    source_date TIMESTAMP,
    price_usd NUMERIC(10,2),
    price_vnd NUMERIC(15,0),
    price_silver_usd NUMERIC(10,2),
    price_silver_vnd NUMERIC(15,0),
    usd_vnd_rate NUMERIC(10,2),
    is_imputed BOOLEAN NOT NULL DEFAULT FALSE,
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    is_missing_from_source BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, timeframe, series_layer, price_timestamp)
);

CREATE TABLE IF NOT EXISTS economic_events (
    id BIGSERIAL PRIMARY KEY,
    event_key VARCHAR(120) NOT NULL UNIQUE,
    event_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    impact_level VARCHAR(20) NOT NULL DEFAULT 'medium',
    impact_score SMALLINT NOT NULL DEFAULT 5,
    summary TEXT NOT NULL,
    price_impact_summary VARCHAR(255),
    is_range_event BOOLEAN NOT NULL DEFAULT FALSE,
    country VARCHAR(50),
    actual_value VARCHAR(120),
    forecast_value VARCHAR(120),
    previous_value VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
