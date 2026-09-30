-- Dados SINTÉTICOS para desenvolvimento, teste e demonstração.
-- Nenhuma pessoa, CPF ou registro aqui corresponde a alguém real
-- (convicção religiosa é dado sensível, LGPD art. 5º, II).
--
-- Contas de teste (todas com a senha: SenhaTeste#2026)
--   fiel1@teste.local        público
--   fiel2@teste.local        público
--   paroquia.a1@teste.local  paroquial, Paróquia São Exemplo (Diocese Alfa)
--   paroquia.a2@teste.local  paroquial, Paróquia Santa Amostra (Diocese Alfa)
--   paroquia.b1@teste.local  paroquial, Paróquia Nossa Senhora do Teste (Diocese Beta)
--   diocese.alfa@teste.local diocesano, Diocese Alfa
--   diocese.beta@teste.local diocesano, Diocese Beta

insert into public.dioceses (id, nome, uf) values
  ('d0000000-0000-0000-0000-00000000000a', 'Diocese Alfa (fictícia)', 'SP'),
  ('d0000000-0000-0000-0000-00000000000b', 'Diocese Beta (fictícia)', 'MG');

insert into public.paroquias (id, diocese_id, nome, endereco, lat, lng) values
  ('a0000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-00000000000a',
   'Paróquia São Exemplo', 'Rua Fictícia, 100, Centro, São Paulo/SP', -23.550520, -46.633308),
  ('a0000000-0000-0000-0000-0000000000a2', 'd0000000-0000-0000-0000-00000000000a',
   'Paróquia Santa Amostra', 'Avenida Imaginária, 200, Pinheiros, São Paulo/SP', -23.567200, -46.692700),
  ('a0000000-0000-0000-0000-0000000000b1', 'd0000000-0000-0000-0000-00000000000b',
   'Paróquia Nossa Senhora do Teste', 'Praça Inventada, 300, Centro, Belo Horizonte/MG', -19.916681, -43.934493);

-- Usuários do Supabase Auth. O trigger ao_criar_usuario cria o perfil público;
-- os perfis paroquiais e diocesanos são promovidos logo abaixo.
do $$
declare
  u record;
begin
  for u in
    select * from (values
      ('10000000-0000-0000-0000-000000000001'::uuid, 'fiel1@teste.local',        'Fiel Sintético Um',      '000.000.001-00'),
      ('10000000-0000-0000-0000-000000000002'::uuid, 'fiel2@teste.local',        'Fiel Sintético Dois',    '000.000.002-00'),
      ('20000000-0000-0000-0000-0000000000a1'::uuid, 'paroquia.a1@teste.local',  'Secretaria São Exemplo', '000.000.003-00'),
      ('20000000-0000-0000-0000-0000000000a2'::uuid, 'paroquia.a2@teste.local',  'Secretaria Santa Amostra','000.000.004-00'),
      ('20000000-0000-0000-0000-0000000000b1'::uuid, 'paroquia.b1@teste.local',  'Secretaria N. S. do Teste','000.000.005-00'),
      ('30000000-0000-0000-0000-00000000000a'::uuid, 'diocese.alfa@teste.local', 'Chancelaria Alfa',       '000.000.006-00'),
      ('30000000-0000-0000-0000-00000000000b'::uuid, 'diocese.beta@teste.local', 'Chancelaria Beta',       '000.000.007-00')
    ) as t(id, email, nome, cpf)
  loop
    insert into auth.users (
      instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
      raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
      confirmation_token, email_change, email_change_token_new, recovery_token
    ) values (
      '00000000-0000-0000-0000-000000000000', u.id, 'authenticated', 'authenticated', u.email,
      extensions.crypt('SenhaTeste#2026', extensions.gen_salt('bf')), now(),
      '{"provider":"email","providers":["email"]}',
      jsonb_build_object('nome', u.nome, 'cpf', u.cpf),
      now(), now(), '', '', '', ''
    );
    insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
    values (gen_random_uuid(), u.id, u.id::text,
            jsonb_build_object('sub', u.id::text, 'email', u.email, 'email_verified', true),
            'email', now(), now(), now());
  end loop;
end;
$$;

update public.perfis set papel = 'paroquial', paroquia_id = 'a0000000-0000-0000-0000-0000000000a1'
  where auth_user_id = '20000000-0000-0000-0000-0000000000a1';
update public.perfis set papel = 'paroquial', paroquia_id = 'a0000000-0000-0000-0000-0000000000a2'
  where auth_user_id = '20000000-0000-0000-0000-0000000000a2';
update public.perfis set papel = 'paroquial', paroquia_id = 'a0000000-0000-0000-0000-0000000000b1'
  where auth_user_id = '20000000-0000-0000-0000-0000000000b1';
update public.perfis set papel = 'diocesano', diocese_id = 'd0000000-0000-0000-0000-00000000000a'
  where auth_user_id = '30000000-0000-0000-0000-00000000000a';
update public.perfis set papel = 'diocesano', diocese_id = 'd0000000-0000-0000-0000-00000000000b'
  where auth_user_id = '30000000-0000-0000-0000-00000000000b';

-- Livros de registro sintéticos.
insert into public.registros_sacramentais
  (id, paroquia_id, tipo, nome_pessoa, data_sacramento, livro, folha, numero, celebrante, padrinhos)
values
  ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a1', 'batismo',
   'Fiel Sintético Um', '1995-03-12', '12', '34', '567', 'Pe. Celebrante Fictício', 'Padrinho Exemplo e Madrinha Exemplo'),
  ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-0000000000a1', 'crisma',
   'Fiel Sintético Um', '2010-08-21', '4', '10', '88', 'Dom Bispo Fictício', 'Padrinho Exemplo'),
  ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-0000000000a1', 'batismo',
   'Pessoa Fictícia Três', '2001-11-02', '13', '5', '610', 'Pe. Celebrante Fictício', 'Madrinha Inventada'),
  ('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-0000000000a2', 'casamento',
   'Noivo Fictício e Noiva Fictícia', '2015-05-30', '7', '22', '140', 'Pe. Outro Fictício', 'Testemunha A e Testemunha B'),
  ('b0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-0000000000b1', 'primeira_comunhao',
   'Fiel Sintético Dois', '2005-10-09', '3', '41', '77', 'Pe. Mineiro Fictício', null);

-- Arrecadação sintética para os painéis.
insert into public.pagamentos (id, tipo, paroquia_id, usuario_id, valor, status, id_transacao_externa)
select v.id, v.tipo, v.paroquia_id, p.id, v.valor, v.status, v.ext
from (values
  ('c0000000-0000-0000-0000-000000000001'::uuid, 'dizimo', 'a0000000-0000-0000-0000-0000000000a1'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 150.00, 'pago', 'seed-1'),
  ('c0000000-0000-0000-0000-000000000002'::uuid, 'dizimo', 'a0000000-0000-0000-0000-0000000000a2'::uuid, '10000000-0000-0000-0000-000000000002'::uuid,  80.00, 'pago', 'seed-2'),
  ('c0000000-0000-0000-0000-000000000003'::uuid, 'dizimo', 'a0000000-0000-0000-0000-0000000000b1'::uuid, '10000000-0000-0000-0000-000000000002'::uuid, 200.00, 'pago', 'seed-3'),
  ('c0000000-0000-0000-0000-000000000004'::uuid, 'taxa_certidao', 'a0000000-0000-0000-0000-0000000000a1'::uuid, '10000000-0000-0000-0000-000000000001'::uuid, 30.00, 'pago', 'seed-4')
) as v(id, tipo, paroquia_id, auth_id, valor, status, ext)
join public.perfis p on p.auth_user_id = v.auth_id;

insert into public.dizimistas (id, perfil_id, paroquia_id)
select 'e0000000-0000-0000-0000-000000000001', id, 'a0000000-0000-0000-0000-0000000000a1'
from public.perfis where auth_user_id = '10000000-0000-0000-0000-000000000001';

insert into public.doacoes (dizimista_id, paroquia_id, pagamento_id) values
  ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a1', 'c0000000-0000-0000-0000-000000000001');

-- Uma solicitação já paga, na fila da Paróquia São Exemplo.
insert into public.solicitacoes_certidao (id, solicitante_id, paroquia_id, tipo, dados_declarados, status, pagamento_id)
select 'f0000000-0000-0000-0000-000000000001', id, 'a0000000-0000-0000-0000-0000000000a1', 'batismo',
       '{"nome_pessoa":"Fiel Sintético Um","data_aproximada":"1995-03","observacoes":"Batizado ainda bebê"}',
       'em_analise', 'c0000000-0000-0000-0000-000000000004'
from public.perfis where auth_user_id = '10000000-0000-0000-0000-000000000001';
