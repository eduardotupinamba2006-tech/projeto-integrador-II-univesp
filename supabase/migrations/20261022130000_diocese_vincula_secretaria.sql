-- O painel diocesano vincula uma conta já cadastrada como secretaria de uma paróquia
-- da própria diocese, e pode desfazer o vínculo. O email das contas fica em auth.users
-- e os perfis de outras pessoas não são visíveis pela RLS, por isso as três operações
-- são funções security definer que conferem, no banco, se quem chama é diocesano
-- da diocese da paróquia.

create function public.secretarias_da_diocese()
returns table (perfil_id uuid, nome text, email text, paroquia_id uuid, paroquia text)
language sql stable security definer set search_path = ''
as $$
  select pf.id, pf.nome, u.email::text, pq.id, pq.nome
  from public.perfis pf
  join auth.users u on u.id = pf.auth_user_id
  join public.paroquias pq on pq.id = pf.paroquia_id
  where pf.papel = 'paroquial'
    and privado.eh_diocesano_de(pq.id)
  order by pq.nome, pf.nome
$$;

create function public.vincular_secretaria(p_email text, p_paroquia_id uuid)
returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_perfil public.perfis;
begin
  if not privado.eh_diocesano_de(p_paroquia_id) then
    raise exception 'Esta paróquia não pertence à sua diocese.' using errcode = '42501';
  end if;

  select pf.* into v_perfil
  from public.perfis pf
  join auth.users u on u.id = pf.auth_user_id
  where lower(u.email) = lower(trim(p_email));

  if v_perfil.id is null then
    raise exception 'Nenhuma conta cadastrada com este email. A pessoa precisa criar a conta no site primeiro.'
      using errcode = 'P0002';
  end if;
  if v_perfil.papel = 'diocesano' then
    raise exception 'Esta conta é de uma diocese e não pode virar secretaria de paróquia.' using errcode = '42501';
  end if;
  -- Secretaria de paróquia de outra diocese continua com a outra diocese.
  if v_perfil.papel = 'paroquial' and not privado.eh_diocesano_de(v_perfil.paroquia_id) then
    raise exception 'Esta conta já é secretaria de uma paróquia de outra diocese.' using errcode = '42501';
  end if;

  update public.perfis
  set papel = 'paroquial', paroquia_id = p_paroquia_id
  where id = v_perfil.id;
end;
$$;

create function public.desvincular_secretaria(p_perfil_id uuid)
returns void
language plpgsql security definer set search_path = ''
as $$
begin
  update public.perfis
  set papel = 'publico', paroquia_id = null
  where id = p_perfil_id
    and papel = 'paroquial'
    and privado.eh_diocesano_de(paroquia_id);
  if not found then
    raise exception 'Secretaria não encontrada nas paróquias da sua diocese.' using errcode = '42501';
  end if;
end;
$$;

revoke all on function public.secretarias_da_diocese() from public, anon;
revoke all on function public.vincular_secretaria(text, uuid) from public, anon;
revoke all on function public.desvincular_secretaria(uuid) from public, anon;
grant execute on function public.secretarias_da_diocese() to authenticated;
grant execute on function public.vincular_secretaria(text, uuid) to authenticated;
grant execute on function public.desvincular_secretaria(uuid) to authenticated;
