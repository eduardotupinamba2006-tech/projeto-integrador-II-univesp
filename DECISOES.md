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

## 5. Backend: decisões da frente 2

- **Data do registro:** 30/09/2026
- **Taxa de emissão:** valor fixo de R$ 30,00 para qualquer sacramento, definido no servidor (`api/_lib/config.py`). O valor enviado pelo navegador é ignorado. O dízimo é cobrado pelo valor integral, sem taxa.
- **Função extra `api/cobranca_pix.py`:** gerar a cobrança Pix exige o token secreto do Mercado Pago, então precisa rodar no servidor. Nenhuma das quatro funções previstas (pdf, webhook, email, validação) cobre essa etapa.
- **PDFs no Storage:** bucket privado `certidoes`, um arquivo por solicitação em `{solicitante_id}/{solicitacao_id}.pdf`. Só o servidor grava; o solicitante lê a própria pasta. O email de aprovação leva um link assinado válido por 7 dias.
- **Database Webhooks via Vault:** os gatilhos de email leem a URL da função e o segredo compartilhado do Vault de cada ambiente, então nada disso fica no repositório. Sem os segredos (Supabase local e CI), os gatilhos não fazem nada.
- **QR Code:** aponta para `/pages/validar.html?c=<id>.<assinatura HMAC-SHA256>`. A validação pública mostra só tipo, nome, data do sacramento, paróquia, diocese e data de emissão.
- **Webhook do Mercado Pago:** valida o cabeçalho `x-signature` e sempre consulta o status real na API do Mercado Pago antes de alterar qualquer coisa. Confere também o valor e o id da transação.

## 6. Frontend: decisões da frente 3

- **Data do registro:** 30/09/2026
- **Pastas:** mantida a convenção que a equipe já usava no painel diocesano. `index.html` fica na raiz; as demais páginas ficam em `pages/`, os estilos em `css/` e os scripts em `js/`, com as funções puras em `js/lib/`, testadas pelo Vitest. A página `pages/dashboard-diocese.html` evoluiu para o painel diocesano completo, e o CSS dela passou a usar seletores com escopo.
- **`/api/config`:** a URL do Supabase e a chave publicável são públicas por natureza, mas mudam entre preview e produção. Como não há etapa de build, o navegador lê esses valores de `/api/config`, que devolve só o que pode ir para o navegador.
- **Servidor de desenvolvimento:** `scripts/servidor_dev.py` (biblioteca padrão do Python) serve as páginas e as funções localmente, lendo `.env.local`, que não é versionado. Existe porque o CLI da Vercel não faz parte da stack. Nunca roda em produção.
- **Login obrigatório para certidão e dízimo:** `solicitacoes_certidao.solicitante_id` e `pagamentos.usuario_id` são obrigatórios e apontam para `perfis`, então quem pede ou doa precisa ter conta. "Com ou sem cadastro como dizimista" se refere ao cadastro em `dizimistas`, que é opcional.
