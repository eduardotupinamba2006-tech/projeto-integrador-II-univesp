-- Storage dos PDFs de certidão e Database Webhooks que disparam os emails.

-- ---------------------------------------------------------------------------
-- Bucket privado das certidões: {solicitante_id}/{solicitacao_id}.pdf
-- Só o servidor grava; o solicitante lê os arquivos da própria pasta.
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('certidoes', 'certidoes', false)
on conflict (id) do nothing;

create policy "certidoes: solicitante lê as próprias" on storage.objects
  for select to authenticated
  using (
    bucket_id = 'certidoes'
    and (storage.foldername(name))[1] = (select privado.meu_perfil_id())::text
  );

-- ---------------------------------------------------------------------------
-- Database Webhooks → api/enviar_email.py
--
-- A URL da função e o segredo compartilhado ficam no Vault de cada ambiente
-- (nunca no repositório):
--   select vault.create_secret('https://<deploy>/api/enviar_email', 'email_webhook_url');
--   select vault.create_secret('<segredo>', 'email_webhook_secret');
-- Sem esses segredos (ex.: Supabase local do CI), o gatilho não faz nada.
-- ---------------------------------------------------------------------------

create extension if not exists pg_net with schema extensions;

create function privado.disparar_webhook_email() returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
  v_url text;
  v_segredo text;
begin
  select decrypted_secret into v_url
    from vault.decrypted_secrets where name = 'email_webhook_url';
  select decrypted_secret into v_segredo
    from vault.decrypted_secrets where name = 'email_webhook_secret';

  if v_url is null or v_segredo is null then
    return new;
  end if;

  perform net.http_post(
    url := v_url,
    body := jsonb_build_object(
      'type', tg_op,
      'schema', tg_table_schema,
      'table', tg_table_name,
      'record', to_jsonb(new),
      'old_record', case when tg_op = 'UPDATE' then to_jsonb(old) end
    ),
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Webhook-Secret', v_segredo
    ),
    timeout_milliseconds := 5000
  );
  return new;
end;
$$;

revoke all on function privado.disparar_webhook_email() from public;

-- Email "aguardando pagamento" (texto varia por tipo).
create trigger email_pagamento_criado
after insert on public.pagamentos
for each row execute function privado.disparar_webhook_email();

-- Recibo de dízimo ou aviso de pedido em análise.
create trigger email_pagamento_confirmado
after update of status on public.pagamentos
for each row
when (old.status is distinct from new.status and new.status = 'pago')
execute function privado.disparar_webhook_email();

-- Certidão aprovada (link do PDF) ou rejeitada (motivo).
create trigger email_solicitacao_revisada
after update of status on public.solicitacoes_certidao
for each row
when (old.status is distinct from new.status and new.status in ('aprovado', 'rejeitado'))
execute function privado.disparar_webhook_email();
