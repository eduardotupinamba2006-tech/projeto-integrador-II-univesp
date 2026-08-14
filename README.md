# Sistema de Emissão de Certidões e Gestão de Dízimo Paroquial

Projeto Integrador II, UNIVESP.

## Sobre o projeto

Sistema web para dioceses e paróquias católicas, com dois módulos principais: emissão de certidão de sacramento (batismo, primeira comunhão, crisma, casamento, ordenação sacerdotal) e gestão de dízimo com pagamento via Pix. Acesso em três níveis, público, paroquial e diocesano, cada um com seu próprio conjunto de permissões sobre os mesmos dados.

## Escopo

### Está dentro desta entrega

- Emissão de certidão, com fluxo de pedido e aprovação contra registro real da paróquia
- Cadastro de dizimista e pagamento de dízimo via Pix
- Painel paroquial (fila de pedidos, registros sacramentais, arrecadação da própria paróquia)
- Painel diocesano (leitura consolidada de todas as paróquias da diocese)
- Autenticação própria, acessibilidade, testes automatizados, CI/CD e deploy gratuito

### Ficou fora, por decisão consciente de escopo

- **Gestão de turmas de catequese.** O projeto original incluía três subsistemas independentes (certidões, dízimo, catequese) além da camada de autenticação em três níveis. Isso é tamanho de sistema de produto para uma equipe, não de entrega acadêmica solo. Catequese fica como próxima fase.
- **Login via gov.br.** O Login Único gov.br é desenhado para integração por órgãos públicos, o processo de solicitação de credencial é conduzido por agente público de um órgão. Uma diocese ou paróquia é uma entidade religiosa de direito privado, não um órgão público, então a aprovação em produção não é realista dentro do prazo do projeto. Login é feito por conta própria (Supabase Auth, email e senha), com papel de acesso definido por um campo no perfil do usuário.

## Arquitetura

Frontend em HTML, CSS e JavaScript puro, sem framework e sem Node no runtime de produção, hospedado na Vercel. As poucas rotinas que precisam rodar protegidas no servidor (nunca no navegador do usuário) são funções Python na própria Vercel: geração do PDF final da certidão, webhook de confirmação de pagamento, e disparo de email. Banco de dados, autenticação e storage ficam no Supabase (Postgres com Row Level Security). Emails transacionais e SMTP customizado do Supabase Auth via Resend. Pagamento via API Pix do Mercado Pago.

```
Navegador (HTML/CSS/JS)
   │
   ├── Supabase Auth ──────── login, papel do usuário
   ├── Supabase Postgres ──── dados, RLS por paroquia_id / diocese_id
   │
   └── Funções Python (Vercel)
          ├── geração de PDF da certidão
          ├── webhook de pagamento (Mercado Pago)
          └── disparo de email (Resend)
```

## Modelo de acesso

| Papel | O que faz |
|---|---|
| Público | Autocadastro livre. Solicita certidão, cadastra-se como dizimista, faz doação, escolhe a paróquia (com busca por proximidade via Google Maps). |
| Paroquial | Conta criada por administrador. Vê e aprova pedidos de certidão da própria paróquia, mantém os registros sacramentais, vê a arrecadação da própria paróquia. |
| Diocesano | Conta criada por administrador. Leitura consolidada de todas as paróquias da diocese, sem edição direta de registro de paróquia. |

Controle de acesso feito via Row Level Security no Postgres, não em lógica de aplicação. Cada tabela sensível carrega `paroquia_id`, e as políticas de RLS comparam esse valor com o papel e a paróquia do usuário autenticado.

## Modelo de dados (núcleo)

```sql
dioceses        (id, nome, uf)
paroquias       (id, diocese_id, nome, endereco, lat, lng)
perfis          (id, auth_user_id, nome, cpf, papel[publico|paroquial|diocesano],
                  paroquia_id, diocese_id)

registros_sacramentais
  (id, paroquia_id, tipo[batismo|primeira_comunhao|crisma|casamento|ordenacao],
   nome_pessoa, data_sacramento, livro, folha, numero, celebrante, padrinhos, criado_por)

pagamentos      (id, tipo[dizimo|taxa_certidao], paroquia_id, usuario_id,
                  valor, metodo, status[pendente|pago|estornado],
                  id_transacao_externa, criado_em)

dizimistas      (id, perfil_id, paroquia_id, cadastrado_em)
doacoes         (id, dizimista_id, paroquia_id, pagamento_id)

solicitacoes_certidao
  (id, solicitante_id, paroquia_id, tipo, dados_declarados jsonb,
   registro_vinculado_id, status[aguardando_pagamento|em_analise|aprovado|rejeitado],
   motivo_rejeicao, pagamento_id, revisado_por, revisado_em, pdf_gerado_em)

emails_enviados (id, destinatario_email, tipo, referencia_tabela, referencia_id,
                  enviado_em, status_envio[enviado|falhou])
```

`registros_sacramentais` é a fonte da verdade. `dados_declarados` é só o que o solicitante digitou ao pedir, nunca é o que vai para o PDF final.

## Fluxos

### Emissão de certidão

1. Usuário público escolhe tipo de sacramento e paróquia (busca por proximidade disponível).
2. Preenche o que lembra do próprio sacramento, confirma o pedido.
3. Sistema mostra a taxa de emissão e gera a cobrança Pix. Pedido nasce com status `aguardando_pagamento`.
4. Webhook confirma o pagamento, status muda para `em_analise`, pedido entra na fila da paróquia.
5. Usuário paroquial busca em `registros_sacramentais`, vincula ou rejeita o pedido (rejeição exige `motivo_rejeicao`).
6. Se vinculado, uma função serverless gera o PDF a partir do registro sacramental, nunca dos dados declarados pelo usuário. Status `aprovado`.

Pedido pago e não encontrado no registro não é reembolsado automaticamente, a taxa cobre o trabalho de busca, não o resultado, prática equivalente à busca em cartório.

### Dízimo

1. Usuário escolhe a paróquia (mesma busca por proximidade), com ou sem se cadastrar como dizimista.
2. Informa o valor, gera cobrança Pix pelo valor integral. Sem taxa de plataforma aqui, o valor doado vai inteiro para a paróquia (descontado apenas o custo de gateway do próprio meio de pagamento, fora do controle do sistema).
3. Webhook confirma pagamento.
4. Painel paroquial soma o arrecadado da própria paróquia, painel diocesano soma entre paróquias.

## Notificações por email

| Evento | Envio |
|---|---|
| Conta criada | Confirmação de cadastro (Supabase Auth) |
| Esqueci a senha | Recuperação de senha (Supabase Auth) |
| `pagamentos` criado | Aguardando pagamento (texto varia por tipo) |
| `pagamentos` confirmado, tipo dízimo | Recibo de doação |
| `pagamentos` confirmado, tipo taxa de certidão | Pagamento confirmado, pedido em análise |
| `solicitacoes_certidao` aprovado | Aprovação, com link do PDF |
| `solicitacoes_certidao` rejeitado | Recusa, com o motivo escrito pela paróquia |

Supabase Auth usa Resend como SMTP customizado (o servidor padrão do Supabase só alcança membros da própria organização do projeto, não serve para usuário público real). Os demais emails são disparados por Database Webhook do Supabase chamando uma função Python que usa a API do Resend diretamente.

## Acessibilidade

Três camadas que se cobrem, não uma solução única:

- HTML semântico e ARIA, para leitor de tela e navegação por teclado.
- VLibras (widget oficial do governo federal, JS puro, sem build) para tradução de texto da página para Libras. Não cobre texto dentro de imagem nem o conteúdo do PDF baixado, só o que está na página.
- axe-core integrado aos testes automatizados (via `@axe-core/playwright`), para pegar regressão de acessibilidade nas duas camadas anteriores.

## Testes

| Camada | Ferramenta | O que cobre |
|---|---|---|
| Frontend | Vitest | Validação de formulário, cálculo de valores, funções puras em JS |
| Funções Python | pytest | Geração de PDF, webhook de pagamento, disparo de email, com mocks |
| Isolamento de RLS | pytest de integração contra Supabase local | Um papel não enxerga nem edita dado de outro papel ou outra paróquia |
| Fim a fim | Playwright, contra preview deploy da Vercel | Cadastro, login, pedido, pagamento sandbox, aprovação, geração de PDF |
| Acessibilidade | axe-core dentro dos testes de Playwright | Regressão de WCAG |

Dado de teste é sempre sintético. Nenhum dado real de paroquiano entra em desenvolvimento, teste ou demonstração.

## CI/CD e deploy

GitHub Actions dispara a cada push: sobe Supabase local via CLI como serviço do próprio workflow, roda Vitest e pytest, aguarda o preview deploy da Vercel, roda Playwright contra ele. Push na `main` vai para produção na Vercel, push em branch ou pull request gera preview automático com URL própria.

Variáveis de ambiente (chaves do Supabase, Resend, Mercado Pago) ficam só no painel da Vercel, nunca no repositório, com valores separados para produção e preview.

Dos dois projetos gratuitos do Supabase, um fica reservado para produção e demonstração. Desenvolvimento e CI usam a instância local via Supabase CLI, para não consumir o segundo projeto à toa.

## Estrutura de pastas

```
/                    páginas HTML, CSS, JS puro
/api/                funções Python (pdf, webhook-pagamento, enviar-email)
/supabase/           migrations, seed de dados sintéticos
/tests/vitest/
/tests/pytest/
/tests/e2e/          Playwright
.github/workflows/
```

## Privacidade e dados

Convicção religiosa é dado pessoal sensível pela LGPD (art. 5º, inciso II), no mesmo grupo de dado de saúde. Combinado com CPF e histórico financeiro de doação, esse sistema concentra uma das combinações mais sensíveis possíveis. Por isso:

- Nenhum dado real de paroquiano é usado fora de produção real e autorizada.
- Ambiente de desenvolvimento, teste e demonstração usa exclusivamente dado sintético.

## Decisões registradas

- **Login próprio, não gov.br.** Inelegibilidade de entidade privada para integração de produção.
- **Catequese fora desta entrega.** Escopo original grande demais para entrega solo.
- **Certidão por aprovação paroquial, não autoatendimento.** É o que dá substância real ao sistema como emissor de certidão, e não gerador de PDF com login na frente.
- **Taxa de plataforma só na certidão, nunca no dízimo.** Cobrar taxa sobre doação religiosa tem peso ético diferente de taxa de emissão de documento, prática já comum em cartório e secretaria paroquial.
- **PDF gerado no servidor, não no navegador.** Geração no cliente é editável via ferramenta de desenvolvedor antes de gerar o arquivo, o que invalida a credibilidade de um documento oficial.
- **Node evitado no runtime de produção, não nas ferramentas de teste.** Vitest e Playwright rodam sobre Node localmente e no CI, isso não aparece no que é servido ao usuário final.

## Roadmap

- Gestão de turmas de catequese
- Solicitação de login gov.br em produção, via patrocínio de órgão público, se viável
- Split de pagamento real por paróquia (hoje o pagamento é centralizado em uma conta, atribuído internamente por `paroquia_id`)
