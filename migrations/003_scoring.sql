-- DealFinderSA deal-scoring schema (Plan 3). Run in Supabase SQL editor AFTER 002.

alter table listings add column if not exists estimated_market_price bigint;
alter table listings add column if not exists deal_delta_zar bigint;
alter table listings add column if not exists deal_delta_pct double precision;
alter table listings add column if not exists deal_score int;
alter table listings add column if not exists deal_confidence text;

create index if not exists listings_deal_score_idx on listings (deal_score);
