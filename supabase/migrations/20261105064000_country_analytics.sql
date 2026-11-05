create table if not exists public.app_usage_events (
    id bigint generated always as identity primary key,
    country_code text not null check (country_code ~ '^[A-Z]{2}$'),
    app_version text not null,
    created_at timestamptz not null default now()
);

alter table public.app_usage_events enable row level security;

revoke all on table public.app_usage_events from anon, authenticated;
grant insert (country_code, app_version) on public.app_usage_events to anon;

drop policy if exists "Allow anonymous country usage inserts"
    on public.app_usage_events;
create policy "Allow anonymous country usage inserts"
    on public.app_usage_events
    for insert
    to anon
    with check (
        country_code ~ '^[A-Z]{2}$'
        and length(app_version) between 1 and 32
    );
