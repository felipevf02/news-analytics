grant select on table public.articles to anon, authenticated;
grant select, insert, update on table public.articles to service_role;
grant usage, select on sequence public.articles_id_seq to service_role;
