# Decisões de projeto

Registro de decisões que divergem do Plano de Ação entregue e validado pela orientadora.

## 1. Frontend em HTML, CSS e JavaScript puro, em vez de Next.js com TypeScript

- **Data do registro:** 29/09/2026
- **Plano de Ação original:** frontend em Next.js com TypeScript.
- **Decisão atual:** frontend em HTML, CSS e JavaScript puro, sem TypeScript, sem framework (React, Vue, Next.js) e sem Node.js em produção. As rotinas que precisam rodar protegidas no servidor são funções Python serverless na Vercel.

### Motivo

- A equipe tem níveis de habilidade variados. HTML/CSS/JS puro é o denominador comum que todos conseguem ler, manter e revisar; Next.js e TypeScript exigiriam curva de aprendizado de build, tipagem, roteamento e renderização no servidor antes de qualquer entrega.
- O escopo real do sistema não precisa dessa complexidade: são poucas páginas, a autorização fica no banco (Row Level Security do Supabase) e não na aplicação, e o processamento sensível (PDF, webhook de pagamento, email) já roda em funções Python isoladas.

### Consequências

- Não há etapa de build para o frontend; a Vercel serve os arquivos estáticos diretamente.
- Node.js continua sendo usado apenas como ferramenta de desenvolvimento e teste (Vitest, Playwright), nunca em produção.
- O cliente do Supabase é carregado no navegador via script de CDN, sem bundler.

## 2. Recriação do schema no Supabase remoto

- **Data do registro:** 29/09/2026
- O projeto remoto tinha as nove tabelas criadas manualmente, fora do modelo de dados oficial: ids `bigint` em vez de `uuid`, tipos `enum` em vez de `check`, sem `criado_em` em `solicitacoes_certidao`, `cpf` e `endereco` aceitando nulo, nenhuma política de RLS e nenhuma migration registrada. Todas estavam vazias.
- **Decisão:** a migration inicial (`supabase/migrations/20260929120000_schema_inicial.sql`) apaga essa versão e recria tudo exatamente como na especificação. A partir daqui, o schema só muda por migration versionada.

## 3. RLS mais restrita que a regra geral "lê e edita"

- **Data do registro:** 29/09/2026
- A regra geral diz que o público e o paroquial "leem e editam" as próprias linhas. Aplicada ao pé da letra, ela deixaria o usuário marcar o próprio pagamento como pago, aprovar a própria certidão ou se promover a diocesano.
- **Decisão:** a leitura segue a regra geral; a escrita foi fechada assim:
  - `pagamentos` e `doacoes`: só o servidor (service role) cria e altera. Usuários só leem.
  - `perfis`: o usuário edita o próprio perfil, mas não `papel`, `paroquia_id` nem `diocese_id`.
  - `solicitacoes_certidao`: o solicitante cria o pedido já em `aguardando_pagamento` e só corrige `dados_declarados` antes de pagar. A paróquia só rejeita (com `motivo_rejeicao` obrigatório); a aprovação passa pela função que gera o PDF, que faz o vínculo com o registro oficial.
  - `dizimistas`: o próprio usuário se cadastra e pode trocar de paróquia. Paroquial e diocesano só leem.
  - `emails_enviados`: sem acesso para usuários, só o servidor.
- As travas de coluna são triggers e as funções auxiliares ficam no schema `privado`, que não é exposto pela API. Nenhuma tabela ganhou ou perdeu coluna.

## 4. Dependências adicionadas

- **Data do registro:** 29/09/2026
- Produção (funções Python): `fpdf2` (PDF da certidão) e `segno` (QR Code). As chamadas HTTP para Supabase, Mercado Pago e Resend usam a biblioteca padrão (`urllib`), sem SDK, e a assinatura do QR Code usa `hmac`.
- Testes Python: `pytest` e `psycopg`.
- Ferramentas de desenvolvimento (Node, nunca em produção): `vitest`, `@playwright/test`, `@axe-core/playwright` e a Supabase CLI (`supabase`).
