-- suburb_stats table
-- Stores bedroom-level median prices from Domain.com.au suburb profiles.
-- Covers QLD, VIC, and any other state where individual sales data isn't free.
-- Run this in the Supabase SQL Editor before running load_domain_suburbs.py

CREATE TABLE IF NOT EXISTS suburb_stats (
    id              BIGSERIAL PRIMARY KEY,
    suburb          TEXT NOT NULL,
    state           TEXT NOT NULL,
    postcode        TEXT,
    property_type   TEXT NOT NULL,   -- 'house', 'apartment', 'townhouse'
    bedrooms        INTEGER,         -- NULL = all bedrooms combined
    median_price    INTEGER,         -- in AUD, e.g. 1450000
    annual_sales    INTEGER,         -- sales in last 12 months
    nearby_suburbs  JSONB,           -- ["bardon", "red hill", "milton", ...]
    source          TEXT DEFAULT 'domain',
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    -- One row per suburb + state + property_type + bedrooms combo
    UNIQUE (suburb, state, property_type, bedrooms)
);

-- Index for the scoring query: filter by suburb + state + property_type
CREATE INDEX IF NOT EXISTS suburb_stats_lookup
    ON suburb_stats (suburb, state, property_type);

-- Index for nearby suburb lookup
CREATE INDEX IF NOT EXISTS suburb_stats_state
    ON suburb_stats (state, property_type);

-- Allow public read (used by the frontend scoring engine)
ALTER TABLE suburb_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read suburb_stats"
    ON suburb_stats FOR SELECT
    TO anon
    USING (true);

-- Allow backend write via service role (used by load_domain_suburbs.py)
GRANT INSERT, UPDATE ON suburb_stats TO service_role;
GRANT USAGE, SELECT ON SEQUENCE suburb_stats_id_seq TO service_role;
