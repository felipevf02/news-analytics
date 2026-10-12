create table if not exists public.article_analyses (
    article_id bigint primary key
        references public.articles(id) on delete cascade,
    analyzer_version text not null,
    word_count integer not null default 0,
    unique_word_count integer not null default 0,
    avg_word_length numeric(6, 2) not null default 0,
    top_terms jsonb not null default '[]'::jsonb,
    analyzed_at timestamptz not null default now()
);

create index if not exists article_analyses_analyzed_at_idx
    on public.article_analyses (analyzed_at desc);

alter table public.article_analyses enable row level security;

grant select on table public.article_analyses to anon, authenticated;
grant select, insert, update on table public.article_analyses to service_role;

drop policy if exists "Public read access to article analyses"
    on public.article_analyses;
create policy "Public read access to article analyses"
    on public.article_analyses
    for select
    to anon, authenticated
    using (true);
