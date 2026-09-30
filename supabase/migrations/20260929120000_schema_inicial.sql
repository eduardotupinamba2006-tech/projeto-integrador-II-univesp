-- Schema inicial do sistema de certidões sacramentais e dízimo paroquial.
--
-- O projeto remoto tinha as tabelas criadas à mão, fora da especificação
-- (ids bigint, tipos enum, sem políticas). Estavam vazias; esta migration
-- remove essa versão e recria tudo conforme o modelo de dados oficial.

drop table if exists
  public.emails_enviados,
  public.solicitacoes_certidao,
  public.doacoes,
  public.dizimistas,
  public.pagamentos,
  public.registros_sacramentais,
  public.perfis,
  public.paroquias,
  public.dioceses
cascade;

drop type if exists
  public.papel_usuario,
  public.status_envio_email,
  public.status_pagamento,
  public.status_solicitacao,
  public.tipo_pagamento,
  public.tipo_sacramento;

-- ---------------------------------------------------------------------------
-- Tabelas
-- ---------------------------------------------------------------------------

create table public.dioceses (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  uf char(2) not null
);

create table public.paroquias (
  id uuid primary key default gen_random_uuid(),
  diocese_id uuid not null references public.dioceses(id),
  nome text not null,
  endereco text not null,
  lat numeric,
  lng numeric
);

create table public.perfis (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid not null references auth.users(id),
  nome text not null,
  cpf text not null,
  papel text not null check (papel in ('publico','paroquial','diocesano')),
  paroquia_id uuid references public.paroquias(id),
  diocese_id uuid references public.dioceses(id)
);

create table public.registros_sacramentais (
  id uuid primary key default gen_random_uuid(),
  paroquia_id uuid not null references public.paroquias(id),
  tipo text not null check (tipo in ('batismo','primeira_comunhao','crisma','casamento','ordenacao')),
  nome_pessoa text not null,
  data_sacramento date not null,
  livro text,
  folha text,
  numero text,
  celebrante text,
  padrinhos text,
  criado_por uuid references public.perfis(id),
  criado_em timestamptz not null default now()
);

create table public.pagamentos (
  id uuid primary key default gen_random_uuid(),
  tipo text not null check (tipo in ('dizimo','taxa_certidao')),
  paroquia_id uuid not null references public.paroquias(id),
  usuario_id uuid not null references public.perfis(id),
  valor numeric not null,
  metodo text not null default 'pix',
  status text not null check (status in ('pendente','pago','estornado')) default 'pendente',
  id_transacao_externa text,
  criado_em timestamptz not null default now()
);

create table public.dizimistas (
  id uuid primary key default gen_random_uuid(),
  perfil_id uuid not null references public.perfis(id),
  paroquia_id uuid not null references public.paroquias(id),
  cadastrado_em timestamptz not null default now()
);

create table public.doacoes (
  id uuid primary key default gen_random_uuid(),
  dizimista_id uuid not null references public.dizimistas(id),
  paroquia_id uuid not null references public.paroquias(id),
  pagamento_id uuid not null references public.pagamentos(id)
);

create table public.solicitacoes_certidao (
  id uuid primary key default gen_random_uuid(),
  solicitante_id uuid not null references public.perfis(id),
  paroquia_id uuid not null references public.paroquias(id),
  tipo text not null check (tipo in ('batismo','primeira_comunhao','crisma','casamento','ordenacao')),
  dados_declarados jsonb not null,
  registro_vinculado_id uuid references public.registros_sacramentais(id),
  status text not null check (status in ('aguardando_pagamento','em_analise','aprovado','rejeitado')) default 'aguardando_pagamento',
  motivo_rejeicao text,
  pagamento_id uuid references public.pagamentos(id),
  revisado_por uuid references public.perfis(id),
  revisado_em timestamptz,
  pdf_gerado_em timestamptz,
  criado_em timestamptz not null default now()
);

create table public.emails_enviados (
  id uuid primary key default gen_random_uuid(),
  destinatario_email text not null,
  tipo text not null,
  referencia_tabela text,
  referencia_id uuid,
  enviado_em timestamptz not null default now(),
  status_envio text not null check (status_envio in ('enviado','falhou'))
);

-- Índices nas colunas usadas pelas políticas de RLS e pelos joins.
create index on public.paroquias (diocese_id);
create index on public.perfis (auth_user_id);
create index on public.registros_sacramentais (paroquia_id);
create index on public.pagamentos (paroquia_id);
create index on public.pagamentos (usuario_id);
create index on public.pagamentos (id_transacao_externa);
create index on public.dizimistas (perfil_id);
create index on public.dizimistas (paroquia_id);
create index on public.doacoes (dizimista_id);
create index on public.doacoes (paroquia_id);
create index on public.solicitacoes_certidao (solicitante_id);
create index on public.solicitacoes_certidao (paroquia_id);

-- ---------------------------------------------------------------------------
-- Funções auxiliares de RLS (schema não exposto pela API)
-- ---------------------------------------------------------------------------

create schema if not exists privado;
revoke all on schema privado from public;
grant usage on schema privado to authenticated, service_role;

create function privado.meu_perfil_id() returns uuid
language sql stable security definer set search_path = ''
as $$ select id from public.perfis where auth_user_id = auth.uid() limit 1 $$;

create function privado.eh_paroquial_de(p_paroquia_id uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.perfis
    where auth_user_id = auth.uid()
      and papel = 'paroquial'
      and paroquia_id = p_paroquia_id
  )
$$;

create function privado.eh_diocesano_de(p_paroquia_id uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1
    from public.perfis pf
    join public.paroquias pq on pq.diocese_id = pf.diocese_id
    where pf.auth_user_id = auth.uid()
      and pf.papel = 'diocesano'
      and pq.id = p_paroquia_id
  )
$$;

-- Verdadeiro quando a operação vem de um usuário final (chave anon ou JWT de
-- usuário). Service role e o dono do banco ficam de fora das travas.
create function privado.eh_usuario_final() returns boolean
language sql stable
as $$ select current_user in ('authenticated', 'anon') $$;

revoke all on all functions in schema privado from public;
grant execute on all functions in schema privado to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Criação automática do perfil público no cadastro (Supabase Auth)
-- ---------------------------------------------------------------------------

create function privado.criar_perfil_publico() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.perfis (auth_user_id, nome, cpf, papel)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'nome', ''),
    coalesce(new.raw_user_meta_data ->> 'cpf', ''),
    'publico'
  );
  return new;
end;
$$;

create trigger ao_criar_usuario
after insert on auth.users
for each row execute function privado.criar_perfil_publico();

-- ---------------------------------------------------------------------------
-- Travas de coluna: impedem que o usuário final altere campos que só o
-- servidor (service role) ou o fluxo de revisão podem alterar.
-- ---------------------------------------------------------------------------

create function privado.proteger_perfil() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if privado.eh_usuario_final()
     and (new.auth_user_id, new.papel, new.paroquia_id, new.diocese_id)
         is distinct from (old.auth_user_id, old.papel, old.paroquia_id, old.diocese_id) then
    raise exception 'papel, paroquia_id e diocese_id não podem ser alterados pelo próprio usuário'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger proteger_perfil
before update on public.perfis
for each row execute function privado.proteger_perfil();

create function privado.proteger_registro() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if not privado.eh_usuario_final() then
    return new;
  end if;
  if tg_op = 'INSERT' then
    new.criado_por := privado.meu_perfil_id();
    new.criado_em := now();
  else
    new.criado_por := old.criado_por;
    new.criado_em := old.criado_em;
  end if;
  return new;
end;
$$;

create trigger proteger_registro
before insert or update on public.registros_sacramentais
for each row execute function privado.proteger_registro();

create function privado.proteger_solicitacao() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if not privado.eh_usuario_final() then
    return new;
  end if;

  -- Um paroquial pode também ser solicitante; o próprio pedido não pago segue a regra do solicitante.
  if privado.eh_paroquial_de(old.paroquia_id)
     and not (old.solicitante_id = privado.meu_perfil_id() and old.status = 'aguardando_pagamento') then
    -- A paróquia só rejeita por aqui; a aprovação passa pela função que gera o PDF.
    if old.status <> 'em_analise' or new.status <> 'rejeitado' then
      raise exception 'a paróquia só pode rejeitar solicitações em análise'
        using errcode = '42501';
    end if;
    if coalesce(btrim(new.motivo_rejeicao), '') = '' then
      raise exception 'motivo_rejeicao é obrigatório para rejeitar'
        using errcode = '23514';
    end if;
    new.revisado_por := privado.meu_perfil_id();
    new.revisado_em := now();
    if (to_jsonb(new) - array['status','motivo_rejeicao','revisado_por','revisado_em'])
       is distinct from
       (to_jsonb(old) - array['status','motivo_rejeicao','revisado_por','revisado_em']) then
      raise exception 'a rejeição só altera status e motivo_rejeicao'
        using errcode = '42501';
    end if;
    return new;
  end if;

  -- Solicitante: só corrige o que declarou enquanto o pagamento não foi feito.
  if (to_jsonb(new) - 'dados_declarados') is distinct from (to_jsonb(old) - 'dados_declarados') then
    raise exception 'o solicitante só pode alterar dados_declarados'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger proteger_solicitacao
before update on public.solicitacoes_certidao
for each row execute function privado.proteger_solicitacao();

create function privado.proteger_dizimista() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if privado.eh_usuario_final()
     and (new.perfil_id, new.cadastrado_em) is distinct from (old.perfil_id, old.cadastrado_em) then
    raise exception 'o dizimista só pode trocar de paróquia'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger proteger_dizimista
before update on public.dizimistas
for each row execute function privado.proteger_dizimista();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.dioceses enable row level security;
alter table public.paroquias enable row level security;
alter table public.perfis enable row level security;
alter table public.registros_sacramentais enable row level security;
alter table public.pagamentos enable row level security;
alter table public.dizimistas enable row level security;
alter table public.doacoes enable row level security;
alter table public.solicitacoes_certidao enable row level security;
alter table public.emails_enviados enable row level security;

-- Dioceses e paróquias são públicas (busca por proximidade sem login).
create policy "dioceses: leitura pública" on public.dioceses
  for select to anon, authenticated using (true);

create policy "paroquias: leitura pública" on public.paroquias
  for select to anon, authenticated using (true);

-- perfis: cada um lê e edita o próprio perfil.
create policy "perfis: dono lê" on public.perfis
  for select to authenticated
  using (auth_user_id = (select auth.uid()));

create policy "perfis: dono edita" on public.perfis
  for update to authenticated
  using (auth_user_id = (select auth.uid()))
  with check (auth_user_id = (select auth.uid()));

-- registros_sacramentais: só a paróquia escreve; a diocese só lê.
create policy "registros: paroquial lê" on public.registros_sacramentais
  for select to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

create policy "registros: diocesano lê" on public.registros_sacramentais
  for select to authenticated
  using (privado.eh_diocesano_de(paroquia_id));

create policy "registros: paroquial insere" on public.registros_sacramentais
  for insert to authenticated
  with check (privado.eh_paroquial_de(paroquia_id));

create policy "registros: paroquial edita" on public.registros_sacramentais
  for update to authenticated
  using (privado.eh_paroquial_de(paroquia_id))
  with check (privado.eh_paroquial_de(paroquia_id));

create policy "registros: paroquial apaga" on public.registros_sacramentais
  for delete to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

-- pagamentos: criados e confirmados só pelo servidor. Usuários só leem.
create policy "pagamentos: dono lê" on public.pagamentos
  for select to authenticated
  using (usuario_id = (select privado.meu_perfil_id()));

create policy "pagamentos: paroquial lê" on public.pagamentos
  for select to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

create policy "pagamentos: diocesano lê" on public.pagamentos
  for select to authenticated
  using (privado.eh_diocesano_de(paroquia_id));

-- dizimistas
create policy "dizimistas: dono lê" on public.dizimistas
  for select to authenticated
  using (perfil_id = (select privado.meu_perfil_id()));

create policy "dizimistas: dono cadastra" on public.dizimistas
  for insert to authenticated
  with check (perfil_id = (select privado.meu_perfil_id()));

create policy "dizimistas: dono edita" on public.dizimistas
  for update to authenticated
  using (perfil_id = (select privado.meu_perfil_id()))
  with check (perfil_id = (select privado.meu_perfil_id()));

create policy "dizimistas: paroquial lê" on public.dizimistas
  for select to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

create policy "dizimistas: diocesano lê" on public.dizimistas
  for select to authenticated
  using (privado.eh_diocesano_de(paroquia_id));

-- doacoes: gravadas pelo servidor quando o dízimo é confirmado.
create policy "doacoes: dono lê" on public.doacoes
  for select to authenticated
  using (exists (
    select 1 from public.dizimistas d
    where d.id = dizimista_id
      and d.perfil_id = (select privado.meu_perfil_id())
  ));

create policy "doacoes: paroquial lê" on public.doacoes
  for select to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

create policy "doacoes: diocesano lê" on public.doacoes
  for select to authenticated
  using (privado.eh_diocesano_de(paroquia_id));

-- solicitacoes_certidao
create policy "solicitacoes: dono lê" on public.solicitacoes_certidao
  for select to authenticated
  using (solicitante_id = (select privado.meu_perfil_id()));

create policy "solicitacoes: dono cria" on public.solicitacoes_certidao
  for insert to authenticated
  with check (
    solicitante_id = (select privado.meu_perfil_id())
    and status = 'aguardando_pagamento'
    and registro_vinculado_id is null
    and pagamento_id is null
    and motivo_rejeicao is null
    and revisado_por is null
    and revisado_em is null
    and pdf_gerado_em is null
  );

create policy "solicitacoes: dono edita antes do pagamento" on public.solicitacoes_certidao
  for update to authenticated
  using (solicitante_id = (select privado.meu_perfil_id()) and status = 'aguardando_pagamento')
  with check (solicitante_id = (select privado.meu_perfil_id()) and status = 'aguardando_pagamento');

create policy "solicitacoes: paroquial lê" on public.solicitacoes_certidao
  for select to authenticated
  using (privado.eh_paroquial_de(paroquia_id));

create policy "solicitacoes: paroquial revisa" on public.solicitacoes_certidao
  for update to authenticated
  using (privado.eh_paroquial_de(paroquia_id))
  with check (privado.eh_paroquial_de(paroquia_id));

create policy "solicitacoes: diocesano lê" on public.solicitacoes_certidao
  for select to authenticated
  using (privado.eh_diocesano_de(paroquia_id));

-- emails_enviados: sem política para usuários; só o servidor (service role) grava e lê.
