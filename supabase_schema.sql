-- ============================================================
-- GetReal — Supabase schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================


-- ── Table 1: suburb_analytics ────────────────────────────────
-- One row per suburb + property_type combination.
-- Pre-calculated medians served as suburb-data.json (fast, no
-- live DB call on every search). Updated via load_vic_data.py.

create table if not exists suburb_analytics (
    id               uuid primary key default gen_random_uuid(),
    suburb           text    not null,   -- lowercase, e.g. 'richmond'
    suburb_display   text    not null,   -- proper case, e.g. 'Richmond'
    state            text    not null,   -- 'VIC', 'NSW', 'QLD', 'WA', 'SA'
    postcode         text,
    property_type    text    not null,   -- 'house', 'townhouse', 'apartment'
    median_price     integer,
    annual_sales     integer,
    price_p25        integer,            -- 25th percentile (estimated)
    price_p75        integer,            -- 75th percentile (estimated)
    data_year        integer,            -- e.g. 2024
    last_updated     timestamptz default now(),
    constraint suburb_analytics_unique unique (suburb, state, property_type)
);

create index if not exists idx_suburb_analytics_lookup
    on suburb_analytics (lower(suburb), state, property_type);

-- Row-level security: public read only
alter table suburb_analytics enable row level security;

create policy "suburb_analytics_public_read"
    on suburb_analytics for select using (true);


-- ── Table 2: property_sales ───────────────────────────────────
-- One row per individual sold property (VIC Valuer General data
-- + enrichment via REA). Used for Phase 2 comparable cards.
-- Rolling 13-month window — old records purged monthly.

create table if not exists property_sales (
    id               uuid primary key default gen_random_uuid(),
    suburb           text    not null,
    state            text    not null,
    postcode         text,
    property_type    text,               -- 'house', 'townhouse', 'apartment'
    sale_price       integer not null,
    sale_date        date    not null,
    address_full     text,
    street_number    text,
    street_name      text,
    bedrooms         integer,            -- null until REA enrichment
    bathrooms        integer,
    car_spaces       integer,
    land_size_sqm    integer,
    streetview_url   text,               -- Google Street View Static API URL
    rea_url          text,               -- REA sold listing URL
    enriched         boolean default false,
    created_at       timestamptz default now()
);

create index if not exists idx_property_sales_suburb
    on property_sales (lower(suburb), state, property_type);

create index if not exists idx_property_sales_date
    on property_sales (sale_date desc);

create index if not exists idx_property_sales_price
    on property_sales (sale_price);

-- Row-level security: public read (sold prices are public record)
alter table property_sales enable row level security;

create policy "property_sales_public_read"
    on property_sales for select using (true);


-- ── Table 3: lead_captures ───────────────────────────────────
-- Stores report requests from the Generate My Report modal.

create table if not exists lead_captures (
    id               uuid primary key default gen_random_uuid(),
    name             text,
    email            text    not null,
    phone            text,
    broker_consent   boolean default false,
    suburb           text,
    property_type    text,
    budget           integer,
    beds             integer,
    baths            integer,
    score            integer,
    created_at       timestamptz default now()
);

-- Leads are private — no public read
alter table lead_captures enable row level security;

-- ============================================================
-- Done. You should see three new tables in Table Editor.
-- ============================================================
