-- Execute no SQL Editor do seu projeto Supabase. Nenhuma senha fica nesta tabela.
begin;

create table if not exists public.atem_perfis (
    id uuid primary key references auth.users(id) on delete cascade,
    nome text not null check (length(trim(nome)) > 0),
    perfil text not null check (perfil in ('especialista', 'supervisor')),
    especialista_id text,
    ativo boolean not null default false,
    constraint especialista_com_vinculo check (
        perfil <> 'especialista'
        or (especialista_id is not null and length(trim(especialista_id)) > 0)
    )
);

alter table public.atem_perfis enable row level security;
alter table public.atem_perfis force row level security;

revoke all on table public.atem_perfis from public, anon, authenticated;
grant select on table public.atem_perfis to authenticated;

drop policy if exists "Ler somente o proprio perfil ativo" on public.atem_perfis;
create policy "Ler somente o proprio perfil ativo"
    on public.atem_perfis for select to authenticated
    using ((select auth.uid()) = id and ativo = true);

commit;

-- Cadastre a conta em Authentication > Users > Add user > Create new user.
-- Depois autorize-a no SQL Editor, substituindo e-mail e nome.
-- A senha deve ser configurada no Supabase Auth, nunca neste SQL.
--
-- insert into public.atem_perfis (id, nome, perfil, especialista_id, ativo)
-- select id, 'Coordenacao', 'supervisor', null, true
-- from auth.users where lower(email) = 'coordenacao@instituicao.org'
-- on conflict (id) do update set nome = excluded.nome, perfil = excluded.perfil,
--     especialista_id = excluded.especialista_id, ativo = excluded.ativo;
--
-- Para especialista, use perfil='especialista' e o ID exato da aba do
-- acompanhamento (ex.: onco-1 ou anest-1), nunca o ID mensal do upload.
-- Não crie políticas INSERT/UPDATE para authenticated: isso permitiria
-- alterar as próprias permissões. Mudanças são administrativas pelo SQL Editor.
