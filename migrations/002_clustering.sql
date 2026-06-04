-- DealFinderSA clustering schema (Plan 2). Run in Supabase SQL editor AFTER 001.

alter table listings add column if not exists fingerprint text;
create index if not exists listings_fingerprint_idx on listings (fingerprint);

create table if not exists price_history (
    id                uuid primary key default gen_random_uuid(),
    source_key        text not null,
    source_listing_id text not null,
    fingerprint       text,
    price_zar         bigint,
    observed_at       timestamptz not null default now()
);
create index if not exists price_history_key_idx on price_history (source_key, source_listing_id);
create index if not exists price_history_fp_idx on price_history (fingerprint);

-- Same-vehicle view: groups valid listings by fingerprint, shows price spread + sources.
create or replace view vehicle_clusters as
select
    fingerprint,
    count(*)                       as listing_count,
    min(price_zar)                 as min_price_zar,
    max(price_zar)                 as max_price_zar,
    array_agg(distinct source_key) as sources,
    max(make)                      as make,
    max(model)                     as model,
    max(year)                      as year
from listings
where is_valid = true and fingerprint is not null
group by fingerprint;
