-- O painel diocesano cadastra novas paróquias, sempre na própria diocese.
-- Edição e exclusão continuam fechadas para usuários (só o servidor ou o dono do banco).

create function privado.eh_diocesano_da_diocese(p_diocese_id uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.perfis
    where auth_user_id = auth.uid()
      and papel = 'diocesano'
      and diocese_id = p_diocese_id
  )
$$;

revoke all on function privado.eh_diocesano_da_diocese(uuid) from public;
grant execute on function privado.eh_diocesano_da_diocese(uuid) to authenticated, service_role;

create policy "paroquias: diocesano cadastra na própria diocese" on public.paroquias
  for insert to authenticated
  with check (privado.eh_diocesano_da_diocese(diocese_id));
