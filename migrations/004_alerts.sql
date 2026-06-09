-- DealFinderSA alerts dedup (Plan 4). Run in Supabase SQL editor AFTER 003.
create table if not exists alerts_sent (
    id                uuid primary key default gen_random_uuid(),
    source_key        text not null,
    source_listing_id text not null,
    deal_score        int,
    sent_at           timestamptz not null default now(),
    unique (source_key, source_listing_id)
);
