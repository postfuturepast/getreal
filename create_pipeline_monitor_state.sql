-- pipeline_monitor_state
-- Tracks the last-known hash and timestamps for each monitored data source.
-- Used by monitor_lookup_data.py to detect changes without re-fetching full pages on every run.

CREATE TABLE IF NOT EXISTS public.pipeline_monitor_state (
    source_key          TEXT PRIMARY KEY,
    url                 TEXT NOT NULL,
    description         TEXT,
    last_hash           TEXT,
    last_checked_at     TIMESTAMPTZ,
    last_changed_at     TIMESTAMPTZ,
    last_auto_updated_at TIMESTAMPTZ,
    last_status         TEXT,          -- 'ok' | 'changed' | 'updated' | 'error'
    last_error          TEXT,
    check_count         INTEGER DEFAULT 0,
    change_count        INTEGER DEFAULT 0
);

ALTER TABLE public.pipeline_monitor_state ENABLE ROW LEVEL SECURITY;

-- Internal pipeline table — service_role only, no public read needed
GRANT SELECT, INSERT, UPDATE ON public.pipeline_monitor_state TO service_role;

-- No public policy — anon users don't need to read pipeline state
