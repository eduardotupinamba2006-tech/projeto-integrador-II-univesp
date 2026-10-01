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
- **API de Orders do Mercado Pago:** a cobrança Pix usa `/v1/orders`, e não `/v1/payments`. A API de Payments recusa contas de teste ("Unauthorized use of live credentials"), e a de Orders é a indicada hoje para o Checkout Transparente. O sandbox usa as credenciais de produção da conta de vendedor de teste. A URL do webhook vem do painel da aplicação, com o evento "Order (Mercado Pago)", porque a API de Orders não aceita `notification_url` na requisição.
- **Comprador de teste no sandbox:** o Mercado Pago recusa o domínio `.local` das contas de demonstração. Enquanto existir a variável `MP_EMAIL_PAGADOR_TESTE` (email de uma conta compradora de teste), a cobrança vai com esse email e com o nome `APRO`, que faz o sandbox aprovar o Pix sozinho em alguns segundos. Assim o fluxo inteiro (pagamento, webhook, pedido em análise, doação) roda de verdade na demonstração. Fora do sandbox a variável é removida e vale o email de quem paga.

## 6. Frontend: decisões da frente 3

- **Data do registro:** 30/09/2026
- **Pastas:** mantida a convenção que a equipe já usava no painel diocesano. `index.html` fica na raiz; as demais páginas ficam em `pages/`, os estilos em `css/` e os scripts em `js/`, com as funções puras em `js/lib/`, testadas pelo Vitest. A página `pages/dashboard-diocese.html` evoluiu para o painel diocesano completo, e o CSS dela passou a usar seletores com escopo.
- **`/api/config`:** a URL do Supabase e a chave publicável são públicas por natureza, mas mudam entre preview e produção. Como não há etapa de build, o navegador lê esses valores de `/api/config`, que devolve só o que pode ir para o navegador.
- **Servidor de desenvolvimento:** `scripts/servidor_dev.py` (biblioteca padrão do Python) serve as páginas e as funções localmente, lendo `.env.local`, que não é versionado. Existe porque o CLI da Vercel não faz parte da stack. Nunca roda em produção.
- **Login obrigatório para certidão e dízimo:** `solicitacoes_certidao.solicitante_id` e `pagamentos.usuario_id` são obrigatórios e apontam para `perfis`, então quem pede ou doa precisa ter conta. "Com ou sem cadastro como dizimista" se refere ao cadastro em `dizimistas`, que é opcional.

## 7. Identidade visual

- **Data do registro:** 30/09/2026
- **Direção:** serviço institucional de confiança, sóbrio e acolhedor, para paroquianos de todas as idades. O azul-cobalto (`#1e3a8a`) que a equipe já usava continua como cor única de destaque, sobre neutros frios. O modo claro e o escuro seguem automaticamente a preferência do sistema.
- **Calibragem:** assimetria 4, movimento 3 e densidade 4, numa escala de 1 a 10. É mais contido que o padrão das skills de design usadas (8/6/4), porque o público inclui idosos e pessoas surdas e o sistema tem formulários e painéis. A animação se resume a transições curtas e a uma entrada suave do conteúdo, e é desligada com `prefers-reduced-motion`.
- **Fonte:** Outfit (licença OFL), hospedada em `/fonts`, sem chamadas ao Google em produção.
- **Ícones:** Phosphor, peso light, carregados do jsDelivr com a versão fixada.
- **Fotos:** a equipe fornece. Os espaços estão documentados em `img/LEIAME.md` e, sem as fotos, aparece um fundo tonal.
- **Verificação:** o axe-core roda em todas as páginas, nos dois modos, dentro da suíte Playwright.

## 8. VLibras

O trecho de instalação que circula em tutoriais (com os `<div vw>` e `new window.VLibras.Widget(...)`) é da versão antiga. A versão 7 do script oficial, `https://vlibras.gov.br/app/vlibras-plugin.js`, monta o botão sozinha dentro de um shadow DOM quando a página carrega. Por isso basta carregar esse script. Ele entra pelo componente `<site-rodape>` (seção 9), e não por um trecho copiado em cada página. Um teste Playwright confere que o botão aparece nas páginas públicas, e o teste do axe-core continua sem violações com o widget presente.

## 9. Cabeçalho e rodapé como componentes

O cabeçalho (com o link "Pular para o conteúdo"), o rodapé e o script do VLibras eram repetidos no HTML das 11 páginas. Agora são dois componentes nativos do navegador (Custom Elements), `<site-cabecalho>` e `<site-rodape>`, definidos em `js/layout.js`. Não há framework nem etapa de build.

- `js/layout.js` é um script clássico no `<head>`, sem `defer`. Assim, os componentes já estão definidos quando o navegador lê o `<body>`, e o cabeçalho aparece montado desde o início, sem piscar.
- Os componentes escrevem no DOM normal, sem shadow DOM, para herdar o `css/estilo.css`. O CSS dá `display: contents` aos dois elementos, e o cabeçalho e o rodapé continuam se comportando como filhos diretos do `body` (layout flex e cabeçalho fixo no topo).
- `<site-cabecalho>` chama `montarCabecalho()` de `js/ui.js`, que monta os links conforme o perfil logado. As páginas não chamam mais essa função. O atributo `sem-menu` tira a navegação da página de validação do QR Code.
- `<site-rodape>` também carrega o VLibras.
- Continua repetido em cada página só o `<head>` (título, fonte, ícones, CSS e `layout.js`), que sem build não tem como ser compartilhado.

O custo é que o cabeçalho e o rodapé passam a depender de JavaScript. Todas as outras páginas do sistema já dependiam dele para funcionar, então não há perda prática.

## 10. Google Maps

- O mapa e a geocodificação usam a Maps JavaScript API, carregada sob demanda por `js/mapa.js` só quando `/api/config` devolve `googleMapsKey`. A chave vai para o navegador de qualquer forma, então a proteção é a restrição por domínio no Google Cloud, e não o sigilo.
- A busca por endereço ou CEP usa o `Geocoder` da própria Maps JavaScript API, com a mesma chave. Não foi criada nenhuma função Python para isso.
- Os marcadores são `AdvancedMarkerElement`, que o teclado alcança, com o Map ID de demonstração do Google (`DEMO_MAP_ID`), coerente com a "chave demo" da especificação.
- O mapa carrega em segundo plano e é complementar: a lista de paróquias continua sendo o caminho principal, inclusive para leitor de tela. Sem a chave, ou se o Google recusar a chave (`gm_authFailure`), o campo de endereço e o mapa somem e a página funciona como antes.
- A chave é restrita ao domínio da Vercel, então localmente, e nos testes Playwright locais, o mapa não aparece.
