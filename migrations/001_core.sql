-- DealFinderSA core schema (Plan 1). Run in Supabase SQL editor.

create table if not exists sources (
    key        text primary key,
    name       text not null,
    tier       int  not null default 1,
    enabled    boolean not null default true,
    base_url   text
);

create table if not exists listings (
    id                uuid primary key default gen_random_uuid(),
    source_key        text not null,
    source_listing_id text not null,
    url               text not null,
    category          text not null,
    title             text,
    make              text,
    model             text,
    variant           text,
    year              int,
    price_zar         bigint,
    mileage_km        int,
    engine_hours      int,
    province          text,
    town              text,
    lat               double precision,
    lng               double precision,
    seller_type       text default 'unknown',
    seller_name       text,
    seller_phone      text,
    description       text,
    image_urls        jsonb default '[]'::jsonb,
    posted_at         timestamptz,
    first_seen_at     timestamptz not null default now(),
    last_seen_at      timestamptz not null default now(),
    status            text not null default 'active',
    is_valid          boolean not null default true,
    quality_flags     jsonb default '[]'::jsonb,
    raw               jsonb,
    unique (source_key, source_listing_id)
);

create index if not exists listings_category_idx on listings (category);
create index if not exists listings_valid_idx on listings (is_valid);

create table if not exists runs (
    id            uuid primary key default gen_random_uuid(),
    started_at    timestamptz not null default now(),
    finished_at   timestamptz,
    source_keys   jsonb default '[]'::jsonb,
    fetched       int default 0,
    upserted      int default 0,
    invalid       int default 0,
    errors        jsonb default '[]'::jsonb
);

create table if not exists sources_health (
    source_key      text primary key,
    last_run_at     timestamptz,
    last_success_at timestamptz,
    listings_found  int default 0,
    errors          text,
    status          text
);

insert into sources (key, name, tier, enabled, base_url)
values ('webuycars', 'WeBuyCars', 1, true, 'https://www.webuycars.co.za')
on conflict (key) do nothing;
